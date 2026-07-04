# Contributing to chrono-rag

Thanks for considering a contribution. This is a small, deliberately simple codebase; the
guidelines below exist to keep it that way.

## Dev setup

```bash
conda create -n chrono-rag python=3.12 -y
conda run -n chrono-rag pip install -e ".[llm,web,mcp,dev]"
conda run -n chrono-rag chrono-rag get-index     # or build your own (README)
conda run -n chrono-rag pytest                   # unit tests (no network needed)
```

The frontend needs Node 18+ (`conda create -n chrono-rag-node -c conda-forge "nodejs>=20"`),
then `cd frontend && npm install && npm test`.

## Architecture in one paragraph

`chrono_rag.core` is the surface-agnostic retrieval core: an in-memory NumPy vector store
(`store.py`), a local ONNX embedder (`embedder.py`), BM25 (`bm25.py`), and hybrid fusion with
an abstention signal (`retrieval.py`, tunables in `config.py`). `chrono_rag.surfaces` holds the
thin adapters: shared formatting (`format.py`), the shared BYOK answer path (`answer.py`), the
CLI (`cli.py`), and the MCP server (`mcp_server.py`); `chrono_rag.webapp` is the FastAPI
backend for the React frontend in `frontend/`. `chrono_rag.preprocess` builds indexes;
`chrono_rag.eval` gates retrieval quality. Rule of thumb: surfaces never reach around the core,
and the core imports no server or LLM SDK.

## Ground rules

1. **Local-first.** Search must keep working with no account, no API key, and (after the
   one-time model download) no network. Features that require a cloud service belong on the
   optional answer path, never in the retrieval core.
2. **No data in git.** Indexes, forum exports, and other build artifacts are release assets,
   not commits (see `.gitignore` and DATA.md). PRs that commit an index will be asked to
   remove it.
3. **Privacy of forum data.** Anything touching `build_forum_index.py` must keep the PII
   scrubbing intact; the scrubber has tests, keep them passing and extend them with new cases.
4. **Honest scope.** The tool targets the PyChrono version stated in the README. Additions
   that mix versions need a plan for not contaminating answers.
5. **Tests + eval.** `pytest` must pass; if you touch retrieval behavior, run
   `python -m chrono_rag.eval.run_eval` against a real index and report the numbers in the PR.

## Practical notes

1. Keep PRs code-only and small; open an issue first for anything structural.
2. Match the existing style (plain Python, type hints, short docstrings that say *why*).
3. Windows matters: paths use `os.path` / `os.pathsep`, console output stays ASCII.
