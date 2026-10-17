"""Installation regressions. Fake subprocesses never invoke conda or touch user envs."""
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import zipfile

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
    promotions = []
    def replace(src, dst):
        # Fail only the first move into dest (the promotion), so the rollback move can run.
        if failure == 'replace' and Path(dst) == dest and not promotions:
            promotions.append(src)
            raise OSError('replacement failed')
        return original_replace(src, dst)
    monkeypatch.setattr(cli, '_download', download)
    monkeypatch.setattr(cli, '_verify_sha256', verify)
    monkeypatch.setattr(cli.os, 'replace', replace)
    assert cli.main(['get-index', '--channel', '10.0.0', '--force']) == (1 if failure else 0)
    manifest = json.loads((dest / 'manifest.json').read_text())
    assert manifest['channel'] == ('main' if failure else '10.0.0')
    assert (dest / 'sentinel').exists() == bool(failure)
    assert not list(tmp_path.glob('.chrono-rag-*'))  # no staging or backup leftovers


def fake_release(monkeypatch, tmp_path, dest, channel='10.0.0'):
    incoming = tmp_path / 'incoming'
    write_index(incoming / 'index', channel)
    archive = shutil.make_archive(str(tmp_path / 'download'), 'zip', incoming)
    monkeypatch.setattr(cli.config, 'index_dir', lambda: str(dest))
    monkeypatch.setattr(cli, '_find_release_asset', lambda _: ('zip-url', 'sha-url'))
    monkeypatch.setattr(cli, '_download', lambda url, path: shutil.copyfile(archive, path))
    monkeypatch.setattr(cli, '_verify_sha256', lambda *args: None)


def sddl(path):
    """DACL of `path` as an SDDL string (Windows). Calls advapi32 directly: Windows PowerShell's
    Get-Acl fails to load when spawned from a PowerShell 7 session, e.g. on CI runners."""
    import ctypes
    advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32')
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    sd, text = ctypes.c_void_p(), ctypes.c_void_p()
    DACL_SECURITY_INFORMATION, SE_FILE_OBJECT, SDDL_REVISION_1 = 4, 1, 1
    err = advapi32.GetNamedSecurityInfoW(str(path), SE_FILE_OBJECT, DACL_SECURITY_INFORMATION,
                                         None, None, None, None, ctypes.byref(sd))
    assert err == 0, f'GetNamedSecurityInfoW({path}) failed: {err}'
    try:
        ok = advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            sd, SDDL_REVISION_1, DACL_SECURITY_INFORMATION, ctypes.byref(text), None)
        assert ok, f'ConvertSecurityDescriptorToStringSecurityDescriptorW failed: {ctypes.get_last_error()}'
        return ctypes.wstring_at(text.value)
    finally:
        kernel32.LocalFree(text)
        kernel32.LocalFree(sd)


@pytest.mark.parametrize('replace_existing', [False, True])
def test_installed_index_gets_ordinary_permissions(monkeypatch, tmp_path, replace_existing):
    """The index must be readable by whoever can read its parent folder.

    Regression: staging inside a tempfile directory gave the index Python's owner-only
    mkdtemp DACL on Windows (3.12.4+), locking the user out after an elevated or
    scheduled-task install."""
    parent = tmp_path / 'clone'
    parent.mkdir()
    dest = parent / 'index'
    if replace_existing:
        write_index(dest, 'main')
    if sys.platform == 'win32':
        # A distinctive inheritable ACE on the parent (Everyone, read) must reach the index.
        subprocess.run(['icacls', str(parent), '/grant', '*S-1-1-0:(OI)(CI)R'], check=True, capture_output=True)
    fake_release(monkeypatch, tmp_path, dest)
    assert cli.main(['get-index', '--channel', '10.0.0', '--force']) == 0
    if sys.platform == 'win32':
        for path in (dest, dest / 'manifest.json'):
            assert re.search(r'\(A;[A-Z]*ID[A-Z]*;[^;]*;;;WD\)', sddl(path)), (path, sddl(path))
    else:
        control = parent / 'control'
        control.mkdir()
        assert stat.S_IMODE(dest.stat().st_mode) == stat.S_IMODE(control.stat().st_mode)


def test_leftover_backup_is_a_warning_not_a_failure(monkeypatch, tmp_path, capsys):
    dest = tmp_path / 'index'
    write_index(dest, 'main')
    fake_release(monkeypatch, tmp_path, dest)
    original_rmtree = cli.shutil.rmtree
    def rmtree(path, *args, **kwargs):
        if Path(path).name.startswith('.chrono-rag-previous-'):  # an old index this user cannot delete
            if kwargs.get('ignore_errors'):
                return
            raise PermissionError(13, 'Access is denied', str(path))
        return original_rmtree(path, *args, **kwargs)
    monkeypatch.setattr(cli.shutil, 'rmtree', rmtree)
    assert cli.main(['get-index', '--channel', '10.0.0', '--force']) == 0
    assert json.loads((dest / 'manifest.json').read_text())['channel'] == '10.0.0'
    assert 'could not delete the previous index' in capsys.readouterr().err


@pytest.mark.parametrize('evil', ['index/../../escape.txt', '../escape.txt', 'ABSOLUTE'])
def test_archive_member_outside_the_index_is_refused(monkeypatch, tmp_path, evil):
    dest = tmp_path / 'clone' / 'index'
    write_index(dest, 'main')
    incoming = tmp_path / 'incoming'
    write_index(incoming / 'index', '10.0.0')
    escape = tmp_path / 'escape.txt'
    archive = tmp_path / 'download.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        for f in (incoming / 'index').iterdir():
            z.write(f, f'index/{f.name}')
        z.writestr(escape.as_posix() if evil == 'ABSOLUTE' else evil, 'escaped')
    monkeypatch.setattr(cli.config, 'index_dir', lambda: str(dest))
    monkeypatch.setattr(cli, '_find_release_asset', lambda _: ('zip-url', 'sha-url'))
    monkeypatch.setattr(cli, '_download', lambda url, path: shutil.copyfile(archive, path))
    monkeypatch.setattr(cli, '_verify_sha256', lambda *args: None)
    assert cli.main(['get-index', '--channel', '10.0.0', '--force']) == 1
    assert not escape.exists() and not (tmp_path / 'clone' / 'escape.txt').exists()
    assert json.loads((dest / 'manifest.json').read_text())['channel'] == 'main'
    assert not list(dest.parent.glob('.chrono-rag-*'))


def test_failed_restore_names_the_surviving_previous_index(monkeypatch, tmp_path, capsys):
    dest = tmp_path / 'index'
    write_index(dest, 'main')
    fake_release(monkeypatch, tmp_path, dest)
    original_replace = cli.os.replace
    def replace(src, dst):
        if Path(dst) == dest:  # both the promotion and the restore fail
            raise OSError('rename blocked')
        return original_replace(src, dst)
    monkeypatch.setattr(cli.os, 'replace', replace)
    assert cli.main(['get-index', '--channel', '10.0.0', '--force']) == 1
    backups = list(tmp_path.glob('.chrono-rag-previous-*'))
    assert len(backups) == 1
    assert json.loads((backups[0] / 'manifest.json').read_text())['channel'] == 'main'
    err = capsys.readouterr().err
    assert 'restoring the previous one failed too' in err and str(backups[0]) in err
