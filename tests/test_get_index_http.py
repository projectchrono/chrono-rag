"""Offline HTTP regressions for the public index downloader."""
from email.utils import formatdate
import hashlib
from http.client import IncompleteRead
import io
import json
import urllib.error
import urllib.request

import pytest

from chrono_rag.surfaces import cli


API_URL = f'https://api.github.com/repos/{cli.config.GITHUB_REPO}/releases?per_page=100&page=1'
ZIP_URL = 'https://github.com/projectchrono/chrono-rag/releases/download/test/index.zip'
SHA_URL = ZIP_URL + '.sha256'
NOW = 1800000000


@pytest.fixture
def http(monkeypatch):
    calls, sleeps = [], []
    responses = []

    def open_url(request, timeout):
        assert timeout == 60
        calls.append(request)
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(urllib.request, 'urlopen', open_url)
    monkeypatch.setattr(cli.time, 'sleep', sleeps.append)
    monkeypatch.setattr(cli.time, 'time', lambda: NOW)
    monkeypatch.setattr(cli.random, 'uniform', lambda *args: 0.5)
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    monkeypatch.delenv('GH_TOKEN', raising=False)
    return responses, calls, sleeps


def http_error(code, reason='test failure', headers=None, body=b''):
    return urllib.error.HTTPError(API_URL, code, reason, headers or {}, io.BytesIO(body))


def invoke(request_name, tmp_path):
    if request_name == 'API listing':
        return cli._find_release_asset('main')
    path = tmp_path / 'index.zip'
    if request_name == '.zip download':
        return cli._download(ZIP_URL, str(path))
    path.write_bytes(b'zip content')
    return cli._verify_sha256(str(path), SHA_URL)


@pytest.mark.parametrize('request_name', ['API listing', '.zip download', '.sha256 fetch'])
def test_503_then_success_for_every_request(http, tmp_path, request_name):
    responses, calls, sleeps = http
    if request_name == 'API listing':
        payload = json.dumps([{'assets': [{'name': 'chrono-rag-index-main-test.zip',
                                          'browser_download_url': ZIP_URL}]}]).encode()
    elif request_name == '.zip download':
        payload = b'zip content'
    else:
        payload = hashlib.sha256(b'zip content').hexdigest().encode()
    responses.extend([http_error(503), io.BytesIO(payload)])
    invoke(request_name, tmp_path)
    assert len(calls) == 2 and sleeps == [1.5]


@pytest.mark.parametrize('code', [429, 500, 502, 503, 504])
def test_transient_status_has_four_attempt_bound(http, code):
    responses, calls, sleeps = http
    responses.extend(http_error(code) for _ in range(4))
    with pytest.raises(RuntimeError, match=f'after 4 attempts: HTTP {code}'):
        cli._find_release_asset('main')
    assert len(calls) == 4 and sleeps == [1.5, 2.5, 4.5]


@pytest.mark.parametrize('signal', ['header', 'body', 'reason'])
def test_rate_limit_near_reset_is_retried(http, signal):
    responses, calls, sleeps = http
    headers = {'X-RateLimit-Reset': str(NOW + 10)}
    if signal == 'header':
        headers['X-RateLimit-Remaining'] = '0'
    responses.extend([http_error(403, 'rate limit exceeded' if signal == 'reason' else 'Forbidden',
                                 headers, b'API rate limit exceeded' if signal == 'body' else b''),
                      io.BytesIO(b'[]')])
    with pytest.raises(FileNotFoundError):  # The successful empty listing has no asset.
        cli._find_release_asset('main')
    assert len(calls) == 2 and sleeps == [10]


def test_rate_limit_far_reset_fails_fast_with_guidance(http, monkeypatch, tmp_path, capsys):
    responses, calls, sleeps = http
    responses.append(http_error(403, 'Forbidden', {'X-RateLimit-Remaining': '0',
                                                 'X-RateLimit-Reset': str(NOW + 3600)}))
    monkeypatch.setattr(cli.config, 'index_dir', lambda: str(tmp_path / 'index'))
    assert cli.main(['get-index']) == 1
    err = capsys.readouterr().err
    for text in ('API listing', API_URL, 'HTTP 403', 'after 1 attempt',
                 'unauthenticated GitHub API limit', 'GITHUB_TOKEN or GH_TOKEN',
                 '2027-01-15 09:00:00 UTC', 'You can also download it manually from'):
        assert text in err
    assert len(calls) == 1 and not sleeps


@pytest.mark.parametrize('code', [401, 403, 404])
def test_permanent_http_errors_are_not_retried(http, code):
    responses, calls, sleeps = http
    responses.append(http_error(code))
    with pytest.raises(RuntimeError, match=f'after 1 attempt: HTTP {code}'):
        cli._find_release_asset('main')
    assert len(calls) == 1 and not sleeps


@pytest.mark.parametrize('retry_after', ['12', formatdate(NOW + 12, usegmt=True)])
def test_retry_after_seconds_and_http_date_are_honored(http, retry_after):
    responses, calls, sleeps = http
    responses.extend([http_error(503, headers={'Retry-After': retry_after}), io.BytesIO(b'[]')])
    with pytest.raises(FileNotFoundError):
        cli._find_release_asset('main')
    assert sleeps == [12]


@pytest.mark.parametrize('error', [urllib.error.URLError('connection failed'), TimeoutError('timed out'),
                                 ConnectionResetError('reset'), IncompleteRead(b'partial')])
def test_network_errors_are_retried(http, error):
    responses, calls, sleeps = http
    responses.extend([error, io.BytesIO(b'[]')])
    with pytest.raises(FileNotFoundError):
        cli._find_release_asset('main')
    assert len(calls) == 2 and sleeps == [1.5]


class InterruptedResponse(io.BytesIO):
    def read(self, size=-1):
        if self.tell():
            raise ConnectionResetError('response interrupted')
        return super().read(4)


def test_interrupted_zip_is_truncated_on_retry_and_checksum_still_gates(http, tmp_path):
    responses, calls, sleeps = http
    responses.extend([InterruptedResponse(b'old partial bytes'), io.BytesIO(b'new'),
                      io.BytesIO(hashlib.sha256(b'new').hexdigest().encode()), io.BytesIO(b'0' * 64)])
    path = tmp_path / 'index.zip'
    cli._download(ZIP_URL, str(path))
    assert path.read_bytes() == b'new'
    cli._verify_sha256(str(path), SHA_URL)
    with pytest.raises(RuntimeError, match='sha256 mismatch'):
        cli._verify_sha256(str(path), SHA_URL)
    assert len(calls) == 4 and sleeps == [1.5]


def test_premature_zip_eof_is_retried(http, tmp_path):
    responses, calls, sleeps = http
    partial = io.BytesIO(b'partial content')
    partial.headers = {'Content-Length': '100'}
    responses.extend([partial, io.BytesIO(b'new')])
    path = tmp_path / 'index.zip'
    cli._download(ZIP_URL, str(path))
    assert path.read_bytes() == b'new'
    assert len(calls) == 2 and sleeps == [1.5]


@pytest.mark.parametrize('request_name', ['API listing', '.sha256 fetch'])
def test_response_read_failure_is_retried(http, tmp_path, request_name):
    responses, calls, sleeps = http

    class FailedRead(io.BytesIO):
        def read(self, size=-1):
            raise TimeoutError('read timed out')

    payload = (b'[]' if request_name == 'API listing' else
               hashlib.sha256(b'zip content').hexdigest().encode())
    responses.extend([FailedRead(), io.BytesIO(payload)])
    if request_name == 'API listing':
        with pytest.raises(FileNotFoundError):
            invoke(request_name, tmp_path)
    else:
        invoke(request_name, tmp_path)
    assert len(calls) == 2 and sleeps == [1.5]


def test_long_retry_after_fails_without_sleeping(http):
    responses, calls, sleeps = http
    responses.append(http_error(429, headers={'Retry-After': '3600'}))
    with pytest.raises(RuntimeError, match='Retry wait exceeds 60 seconds'):
        cli._find_release_asset('main')
    assert len(calls) == 1 and not sleeps


def test_invalid_retry_after_uses_backoff(http):
    responses, calls, sleeps = http
    responses.extend([http_error(503, headers={'Retry-After': 'invalid'}), io.BytesIO(b'[]')])
    with pytest.raises(FileNotFoundError):
        cli._find_release_asset('main')
    assert sleeps == [1.5]


@pytest.mark.parametrize('request_name,url', [('API listing', API_URL), ('.zip download', ZIP_URL),
                                            ('.sha256 fetch', SHA_URL)])
def test_final_error_names_request_url_and_attempt_count(http, tmp_path, request_name, url):
    responses, calls, sleeps = http
    responses.extend(urllib.error.URLError('offline') for _ in range(4))
    with pytest.raises(RuntimeError) as exc:
        invoke(request_name, tmp_path)
    for text in (request_name, url, 'after 4 attempts', 'URLError', 'offline'):
        assert text in str(exc.value)


@pytest.mark.parametrize('token_env', ['GITHUB_TOKEN', 'GH_TOKEN', 'both'])
def test_token_is_sent_only_to_https_api_host(http, monkeypatch, token_env):
    responses, calls, sleeps = http
    if token_env in ('GITHUB_TOKEN', 'both'):
        monkeypatch.setenv('GITHUB_TOKEN', 'github-test-token')
    if token_env in ('GH_TOKEN', 'both'):
        monkeypatch.setenv('GH_TOKEN', 'gh-test-token')
    urls = [API_URL, ZIP_URL, SHA_URL, 'https://api.github.com.evil.invalid/releases',
            'http://api.github.com/releases']
    responses.extend(io.BytesIO() for _ in urls)
    for url in urls:
        cli._http_get(url).close()
    expected = 'gh-test-token' if token_env == 'GH_TOKEN' else 'github-test-token'
    assert calls[0].get_header('Authorization') == f'Bearer {expected}'
    assert all(request.get_header('Authorization') is None for request in calls[1:])
    assert all(request.get_header('User-agent') == 'chrono-rag' for request in calls)


def test_api_request_without_token_remains_anonymous(http):
    responses, calls, sleeps = http
    responses.append(io.BytesIO())
    cli._http_get(API_URL).close()
    assert calls[0].get_header('Authorization') is None


def test_authenticated_rate_limit_message_does_not_expose_token(http, monkeypatch):
    responses, calls, sleeps = http
    monkeypatch.setenv('GITHUB_TOKEN', 'secret-test-token')
    responses.append(http_error(403, 'rate limit exceeded',
                                {'X-RateLimit-Reset': str(NOW + 3600)}))
    with pytest.raises(RuntimeError) as exc:
        cli._find_release_asset('main')
    assert 'rate limit for the supplied token' in str(exc.value)
    assert 'secret-test-token' not in str(exc.value)


@pytest.mark.parametrize('token_env', ['GITHUB_TOKEN', 'GH_TOKEN'])
def test_rejected_token_falls_back_to_anonymous_success(http, monkeypatch, capsys, token_env):
    responses, calls, sleeps = http
    monkeypatch.setenv(token_env, 'stale-secret-token')
    payload = json.dumps([{'assets': [{'name': 'chrono-rag-index-main-test.zip',
                                      'browser_download_url': ZIP_URL}]}]).encode()
    responses.extend([http_error(401, 'Bad credentials'), io.BytesIO(payload)])
    assert cli._find_release_asset('main') == (ZIP_URL, None)
    assert calls[0].get_header('Authorization') == 'Bearer stale-secret-token'
    assert calls[1].get_header('Authorization') is None
    warning = capsys.readouterr().err
    assert len(warning.splitlines()) == 1
    assert 'token was rejected' in warning and 'continued unauthenticated' in warning
    assert 'stale-secret-token' not in warning
    assert not sleeps
    assert cli.os.environ[token_env] == 'stale-secret-token'


def test_rejected_token_then_anonymous_rate_limit_has_guidance(http, monkeypatch, capsys):
    responses, calls, sleeps = http
    monkeypatch.setenv('GITHUB_TOKEN', 'stale-secret-token')
    responses.extend([http_error(401, 'Bad credentials'),
                      http_error(403, 'Forbidden', {'X-RateLimit-Remaining': '0',
                                                    'X-RateLimit-Reset': str(NOW + 3600)})])
    with pytest.raises(RuntimeError) as exc:
        cli._find_release_asset('main')
    for text in ('unauthenticated GitHub API limit', 'GITHUB_TOKEN or GH_TOKEN',
                 '2027-01-15 09:00:00 UTC', 'after 2 attempts', API_URL):
        assert text in str(exc.value)
    assert calls[1].get_header('Authorization') is None
    assert 'stale-secret-token' not in str(exc.value) + capsys.readouterr().err
    assert len(calls) == 2 and not sleeps


def test_rejected_token_stays_disabled_during_transient_retries(http, monkeypatch, capsys):
    responses, calls, sleeps = http
    monkeypatch.setenv('GITHUB_TOKEN', 'stale-secret-token')
    responses.extend([http_error(401, 'Bad credentials'),
                      http_error(403, 'Forbidden', {'X-RateLimit-Remaining': '0',
                                                    'X-RateLimit-Reset': str(NOW + 10)})])
    responses.extend(http_error(503) for _ in range(3))
    with pytest.raises(RuntimeError, match='after 5 attempts: HTTP 503'):
        cli._find_release_asset('main')
    assert len(calls) == 5 and sleeps == [10, 2.5, 4.5]
    assert all(request.get_header('Authorization') is None for request in calls[1:])
    assert len(capsys.readouterr().err.splitlines()) == 1


def test_anonymous_401_after_token_rejection_is_permanent(http, monkeypatch, capsys):
    responses, calls, sleeps = http
    monkeypatch.setenv('GITHUB_TOKEN', 'stale-secret-token')
    responses.extend(http_error(401, 'Bad credentials') for _ in range(2))
    with pytest.raises(RuntimeError, match='after 2 attempts: HTTP 401'):
        cli._find_release_asset('main')
    assert len(calls) == 2 and not sleeps
    assert len(capsys.readouterr().err.splitlines()) == 1


def test_download_401_does_not_trigger_token_fallback(http, monkeypatch, capsys):
    responses, calls, sleeps = http
    monkeypatch.setenv('GITHUB_TOKEN', 'stale-secret-token')
    responses.append(http_error(401, 'Unauthorized'))
    with pytest.raises(RuntimeError, match='after 1 attempt: HTTP 401'):
        cli._retry_get(ZIP_URL, '.zip download', lambda resp: resp.read())
    assert calls[0].get_header('Authorization') is None
    assert len(calls) == 1 and not sleeps
    assert not capsys.readouterr().err
