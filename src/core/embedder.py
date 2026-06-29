"""Pluggable local text embedder.

Wraps fastembed (ONNX runtime, no torch) so the install is light and cold start
is fast. The same model is used to build the index and to embed queries; the
chosen model name is recorded in the index manifest and must match at query time.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

import numpy as np

# Candidates benchmarked by the eval harness. bge-small is what chrono-oracle
# proved out; nomic is the code-aware alternative.
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


def _l2_normalize(arr: np.ndarray) -> np.ndarray:
    """L2-normalize so a dot product equals cosine similarity. Idempotent."""
    if arr.ndim == 1:
        norm = float(np.linalg.norm(arr)) or 1.0
        return (arr / norm).astype(np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (arr / norms).astype(np.float32)


class Embedder:
    """ONNX text embedder via fastembed. Documents and queries use the model's
    own passage/query formatting (e.g. bge's retrieval instruction)."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - install-time guard
            raise ImportError(
                "fastembed is required for the local embedder. "
                "Install it with `pip install fastembed`."
            ) from exc
        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)
        probe = next(iter(self._model.query_embed("dimension probe")))
        self._dim = int(np.asarray(probe).shape[-1])

    @property
    def dim(self) -> int:
        return self._dim

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        """Embed a batch of passages -> (N, dim) float32, L2-normalized."""
        vecs = list(self._model.embed(texts))
        return _l2_normalize(np.asarray(vecs, dtype=np.float32))

    def embed_query(self, text: str) -> np.ndarray:
        """Embed one query -> (dim,) float32, L2-normalized."""
        vec = next(iter(self._model.query_embed(text)))
        return _l2_normalize(np.asarray(vec, dtype=np.float32))


_OPENAI_MODELS = frozenset({
    "text-embedding-3-small",
    "text-embedding-3-large",
    "text-embedding-ada-002",
})


class OpenAIEmbedder:
    """Query embedder backed by the OpenAI Embeddings API.

    Used automatically when the index manifest names an OpenAI model.
    Requires OPENAI_API_KEY in the environment.
    """

    def __init__(self, model_name: str) -> None:
        try:
            import openai as _openai
        except ImportError as exc:
            raise ImportError(
                "openai is required for OpenAI-backed indexes. "
                "Install it with `pip install openai`."
            ) from exc
        self.model_name = model_name
        self._client = _openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @property
    def dim(self) -> int:
        # fixed per model; avoids an API round-trip at init time
        return {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}.get(
            self.model_name, 1536
        )

    def embed_query(self, text: str) -> np.ndarray:
        resp = self._client.embeddings.create(model=self.model_name, input=text)
        vec = np.asarray(resp.data[0].embedding, dtype=np.float32)
        return _l2_normalize(vec)


@lru_cache(maxsize=4)
def get_embedder(model_name: str = DEFAULT_MODEL) -> "Embedder | OpenAIEmbedder":
    """Return a cached embedder. Dispatches to OpenAIEmbedder for OpenAI model names,
    otherwise uses the local fastembed Embedder."""
    if model_name in _OPENAI_MODELS:
        return OpenAIEmbedder(model_name)
    return Embedder(model_name)
