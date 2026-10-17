"""The loaded index's scope must reach the model and every answer surface."""
from types import SimpleNamespace

import pytest

from chrono_rag.surfaces import answer, cli


@pytest.fixture(params=['PyChrono 10.0', 'Chrono main snapshot 2026-10-17 (post-10.0 development)'])
def captured_answer(monkeypatch, request):
    scope = request.param
    captured = {}
    retrieval = SimpleNamespace(version_label=scope, insufficient_evidence=False,
                                results=[SimpleNamespace(path='example.py', line=1, language='py', text='code')])
    monkeypatch.setattr(answer, 'get_core', lambda: SimpleNamespace(search=lambda *a, **k: retrieval))
    class FakeLLM:
        model, provider = 'test', 'test'
        def __init__(self, **kwargs): pass
        def complete(self, **kwargs):
            captured.update(kwargs)
            return 'Use ChBody.'
    monkeypatch.setattr('chrono_rag.inference.llm.LLM', FakeLLM)
    return scope, captured, retrieval


def test_answer_scope_reaches_prompt_and_response(captured_answer):
    scope, captured, _ = captured_answer
    response = answer.answer('rigid body')
    assert response['version'] == scope
    assert f'Index scope: {scope}' in captured['system']
    assert 'from Chrono/PyChrono 10.0' not in captured['system']


def test_abstention_preserves_scope_without_model_call(captured_answer):
    scope, captured, retrieval = captured_answer
    retrieval.insufficient_evidence = True
    response = answer.answer('off topic')
    assert response['version'] == scope and response['insufficient']
    assert not captured


def test_cli_prints_scope(captured_answer, capsys):
    scope, _, _ = captured_answer
    assert cli.main(['ask', 'rigid body']) == 0
    assert f'[scope] {scope}' in capsys.readouterr().out


def test_web_preserves_scope(captured_answer):
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from chrono_rag.webapp import app
    scope, _, _ = captured_answer
    response = TestClient(app).post('/search', json={'query': 'rigid body'})
    assert response.status_code == 200
    assert response.json()['version'] == scope
