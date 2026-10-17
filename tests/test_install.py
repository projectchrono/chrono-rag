"""Installation regressions. Fake subprocesses never invoke conda or touch user envs."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from chrono_rag.surfaces import cli

spec = importlib.util.spec_from_file_location('setup_env', Path(__file__).parents[1] / 'scripts/setup_env.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def fake_conda(monkeypatch, tmp_path, existing=True, fail=None):
    calls = []
    prefix = str(tmp_path / 'envs' / 'test-rag')

    def run(args, **kwargs):
        assert kwargs['check'] is True
        calls.append(args)
        stage = ('list' if args[1:3] == ['env', 'list'] else
                 'info' if args[1] == 'info' else
                 'create' if args[1] == 'create' else
                 'install' if 'pip' in args else 'index')
        if stage == fail:
            raise subprocess.CalledProcessError(1, args)
        output = ({'envs': [prefix] if existing else []} if stage == 'list' else
                  {'envs_dirs': [str(tmp_path / 'envs')]} if stage == 'info' else {})
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(output))

    monkeypatch.setattr(bootstrap.subprocess, 'run', run)
    return calls, prefix


@pytest.mark.parametrize('existing', [True, False])
def test_setup_reuses_environment_and_requests_selected_channel(monkeypatch, tmp_path, existing, capsys):
    calls, prefix = fake_conda(monkeypatch, tmp_path, existing)
    bootstrap.setup('fake-conda', 'test-rag', '10.0.0')
    assert sum(c[1] == 'create' for c in calls) == (0 if existing else 1)
    if existing:
        assert ['-p', prefix] == calls[-1][3:5]
    assert calls[-1][-3:] == ['--channel', '10.0.0', '--if-missing']
    assert 'is ready' in capsys.readouterr().out


@pytest.mark.parametrize('stage', ['list', 'info', 'create', 'install', 'index'])
def test_setup_never_reports_ready_after_failure(monkeypatch, tmp_path, stage, capsys):
    calls, _ = fake_conda(monkeypatch, tmp_path, existing=False, fail=stage)
    with pytest.raises(subprocess.CalledProcessError):
        bootstrap.setup('fake-conda', 'test-rag', 'main')
    assert 'is ready' not in capsys.readouterr().out
    assert len(calls) == ['list', 'info', 'create', 'install', 'index'].index(stage) + 1


def test_setup_refuses_unregistered_existing_directory(monkeypatch, tmp_path):
    calls, prefix = fake_conda(monkeypatch, tmp_path, existing=False)
    Path(prefix).mkdir(parents=True)
    sentinel = Path(prefix) / 'keep.txt'
    sentinel.write_text('keep')
    with pytest.raises(ValueError, match='directory already exists'):
        bootstrap.setup('fake-conda', 'test-rag', 'main')
    assert not any(c[1] == 'create' for c in calls)
    assert sentinel.read_text() == 'keep'


def test_setup_entrypoint_exits_nonzero_on_install_failure(monkeypatch, tmp_path, capsys):
    fake_conda(monkeypatch, tmp_path, fail='install')
    monkeypatch.setattr(bootstrap.sys, 'argv', ['setup_env.py', '--conda', 'fake', '--env', 'test-rag'])
    assert bootstrap.main() == 1
    output = capsys.readouterr()
    assert 'Setup failed' in output.err
    assert 'is ready' not in output.out


def write_index(path, channel='main'):
    path.mkdir(parents=True, exist_ok=True)
    np.save(path / 'embeddings.npy', np.array([[1, 0, 0]], dtype=np.float32))
    (path / 'meta.jsonl').write_text(json.dumps({'text': 'body', 'path': 'demo.py'}) + '\n')
    (path / 'manifest.json').write_text(json.dumps({'model': 'fake', 'dim': 3, 'n_chunks': 1,
                                                 'channel': channel, 'version_label': channel}))


def test_reuse_valid_index_is_offline_and_wrong_channel_is_rejected(monkeypatch, tmp_path):
    dest = tmp_path / 'index'
    write_index(dest)
    monkeypatch.setattr(cli.config, 'index_dir', lambda: str(dest))
    monkeypatch.setattr(cli, '_http_get', lambda _: pytest.fail('must not access network'))
    assert cli.main(['get-index', '--if-missing']) == 0
    assert cli.main(['get-index', '--channel', '10.0.0', '--if-missing']) == 1
    (dest / 'meta.jsonl').unlink()
    assert cli.main(['get-index', '--if-missing']) == 1


def release(channel):
    name = f'chrono-rag-index-{channel}-abcdef.zip'
    return {'assets': [{'name': name, 'browser_download_url': name},
                       {'name': name + '.sha256', 'browser_download_url': name + '.sha256'}]}


def test_release_lookup_pages_back_to_pinned_channel(monkeypatch):
    calls = []
    def get(url):
        calls.append(url)
        rows = [release('main')] * 100 if len(calls) == 1 else [release('10.0.0')]
        return io.BytesIO(json.dumps(rows).encode())
    monkeypatch.setattr(cli, '_http_get', get)
    assert cli._find_release_asset('10.0.0')[0] == 'chrono-rag-index-10.0.0-abcdef.zip'
    assert len(calls) == 2 and 'page=2' in calls[-1]


def test_missing_channel_does_not_fall_back_to_main_or_legacy(monkeypatch):
    rows = [release('main'), {'assets': [{'name': 'chrono-rag-index-8baad0e.zip'}]}]
    monkeypatch.setattr(cli, '_http_get', lambda _: io.BytesIO(json.dumps(rows).encode()))
    with pytest.raises(FileNotFoundError, match="no '10.0.0'"):
        cli._find_release_asset('10.0.0')


@pytest.mark.parametrize('failure', ['download', 'checksum', 'wrong-channel', 'replace', None])
def test_channel_switch_preserves_old_index_on_failure(monkeypatch, tmp_path, failure):
    dest = tmp_path / 'installed'
    write_index(dest, 'main')
    (dest / 'sentinel').write_text('original')
    incoming = tmp_path / 'incoming'
    write_index(incoming / 'index', 'main' if failure == 'wrong-channel' else '10.0.0')
    archive = shutil.make_archive(str(tmp_path / 'download'), 'zip', incoming)
    monkeypatch.setattr(cli.config, 'index_dir', lambda: str(dest))
    monkeypatch.setattr(cli, '_find_release_asset', lambda _: ('zip-url', 'sha-url'))
    def download(url, path):
        if failure == 'download':
            raise OSError('download failed')
        shutil.copyfile(archive, path)
    def verify(*args):
        if failure == 'checksum':
            raise RuntimeError('sha256 mismatch')
    original_replace = cli.os.replace
    def replace(src, dst):
        if failure == 'replace' and Path(src).name == 'index':
            raise OSError('replacement failed')
        return original_replace(src, dst)
    monkeypatch.setattr(cli, '_download', download)
    monkeypatch.setattr(cli, '_verify_sha256', verify)
    monkeypatch.setattr(cli.os, 'replace', replace)
    assert cli.main(['get-index', '--channel', '10.0.0', '--force']) == (1 if failure else 0)
    manifest = json.loads((dest / 'manifest.json').read_text())
    assert manifest['channel'] == ('main' if failure else '10.0.0')
    assert (dest / 'sentinel').exists() == bool(failure)
