from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

load_dotenv()

from preprocess.dataparser import parse_mbox, parse_repos
from preprocess.embeddings import generate_embeddings
from preprocess.vectorstore import create_vector_search_index, upsert_documents
from inference.vector_search import search

_REPOS_DIR = os.getenv(
    "REPOS_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../pychrono-examples-9.0"),
)

_MBOX_PATH = os.getenv(
    "MBOX_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../topics.mbox"),
)

app = FastAPI(title="Chrono RAG API")


# ---------- /index ----------

class IndexResponse(BaseModel):
    chunks_indexed: int


@app.post("/index", response_model=IndexResponse, summary="Parse repos, embed, and upsert into MongoDB")
def index() -> IndexResponse:
    documents = []
    try:
        documents = list(parse_repos(_REPOS_DIR))
        if os.path.exists(_MBOX_PATH):
            documents.extend(parse_mbox(_MBOX_PATH))
        documents = generate_embeddings(documents)
        upsert_documents(documents)
        try:
            create_vector_search_index()
        except Exception:
            pass  # index already exists
        return IndexResponse(chunks_indexed=len(documents))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------- /search ----------

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchResponse(BaseModel):
    answer: str


@app.post("/search", response_model=SearchResponse, summary="Vector search + LLM answer")
def vector_search(body: SearchRequest) -> SearchResponse:
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")
    try:
        answer = search(body.query, top_k=body.top_k)
        return SearchResponse(answer=answer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)