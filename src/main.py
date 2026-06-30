"""Chrono RAG v2 - FastAPI web surface.

Local, bring-your-own-key answer service over the retrieval core. No MongoDB, no
indexing endpoint (the index is built offline by preprocess/build_index.py). The
React frontend posts to /search; /retrieve returns raw chunks for tooling.

Run:
  conda run -n chrono-rag python -m uvicorn main:app --app-dir src --port 8000
"""
from __future__ import annotations

import os
import sys

# Bootstrap so `from core ...` works whether launched via --app-dir src or directly.
_SRC = os.path.dirname(os.path.abspath(__file__))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

from surfaces.answer import answer as run_answer
from surfaces.format import get_core

app = FastAPI(title="Chrono RAG v2")


class SearchRequest(BaseModel):
    query: str
    top_k: int = 8
    model: str | None = None


class SearchResponse(BaseModel):
    answer: str
    sources: list[str] = []
    insufficient: bool = False


@app.post("/search", response_model=SearchResponse, summary="Retrieve + BYOK LLM answer")
def search(body: SearchRequest) -> SearchResponse:
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")
    try:
        res = run_answer(body.query, k=body.top_k, model=body.model)
        return SearchResponse(answer=res["answer"], sources=res["sources"], insufficient=res["insufficient"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 8


@app.post("/retrieve", summary="Retrieve raw chunks (no LLM, no key)")
def retrieve(body: RetrieveRequest):
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")
    r = get_core().search(body.query, k=body.top_k)
    return {
        "version": r.version_label,
        "insufficient_evidence": r.insufficient_evidence,
        "confidence": r.confidence,
        "results": [vars(res) for res in r.results],
    }


@app.get("/health", summary="Liveness + index info")
def health():
    core = get_core()
    return {"status": "ok", "chunks": len(core.store), "manifest": core.store.manifest}
