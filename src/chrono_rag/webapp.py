"""Chrono RAG - FastAPI web surface.

Local, bring-your-own-key answer service over the retrieval core. The React
frontend posts to /search; /retrieve returns raw chunks for tooling.

Run (from the repo root, after `pip install -e .[web,llm]`):
  python -m uvicorn chrono_rag.webapp:app --port 8000
"""
from __future__ import annotations

import logging

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

load_dotenv()

from chrono_rag.surfaces.answer import answer as run_answer  # noqa: E402
from chrono_rag.surfaces.format import get_core  # noqa: E402

log = logging.getLogger("chrono_rag.webapp")

app = FastAPI(title="Chrono RAG")

# Manifest keys safe to expose on /health (no local filesystem paths).
_HEALTH_MANIFEST_KEYS = ("model", "dim", "n_chunks", "chrono_version",
                         "version_label", "commit", "chunker_version")


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=8, ge=1, le=25)
    model: str | None = None
    provider: str | None = None


class SearchResponse(BaseModel):
    answer: str
    sources: list[str] = []
    insufficient: bool = False
    model: str | None = None
    provider: str | None = None


@app.post("/search", response_model=SearchResponse, summary="Retrieve + BYOK LLM answer")
def search(body: SearchRequest) -> SearchResponse:
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")
    try:
        res = run_answer(body.query, k=body.top_k, model=body.model, provider=body.provider)
        return SearchResponse(
            answer=res["answer"],
            sources=res["sources"],
            insufficient=res["insufficient"],
            model=res.get("model"),
            provider=res.get("provider"),
        )
    except ValueError as exc:  # configuration problems are the user's to fix
        raise HTTPException(status_code=400, detail=f"configuration error: {exc}")
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="no search index found on the server; run `chrono-rag get-index` "
                   "(or set CHRONO_RAG_INDEX) and restart",
        )
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="the answer LLM SDK is not installed on the server; "
                   "install with `pip install -e .[llm]` and restart",
        )
    except Exception as exc:
        log.exception("answer failed")
        detail = "the LLM call failed"
        low = str(exc).lower()
        if any(s in low for s in ("401", "auth", "api key", "api_key", "permission")):
            detail = ("the LLM call failed: the server has no valid API key. Set "
                      "ANTHROPIC_API_KEY / OPENAI_API_KEY (e.g. in a .env file), or "
                      "configure a local server via CHRONO_RAG_LLM_*")
        raise HTTPException(status_code=500, detail=detail)


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = Field(default=8, ge=1, le=25)


@app.post("/retrieve", summary="Retrieve raw chunks (no LLM, no key)")
def retrieve(body: RetrieveRequest):
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")
    try:
        r = get_core().search(body.query, k=body.top_k)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="no search index found on the server")
    return {
        "version": r.version_label,
        "insufficient_evidence": r.insufficient_evidence,
        "confidence": r.confidence,
        "results": [vars(res) for res in r.results],
    }


@app.get("/health", summary="Liveness + index info")
def health():
    try:
        core = get_core()
    except FileNotFoundError:
        return {"status": "no-index", "chunks": 0, "manifest": {}}
    manifest = {k: v for k, v in core.store.manifest.items() if k in _HEALTH_MANIFEST_KEYS}
    return {"status": "ok", "chunks": len(core.store), "manifest": manifest}
