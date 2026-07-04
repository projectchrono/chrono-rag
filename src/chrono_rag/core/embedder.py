"""Pluggable local text embedder.

Wraps fastembed (ONNX runtime, no torch) so the install is light and cold start
is fast. The same model is used to build the index and to embed queries; the
chosen model name is recorded in the index manifest and must match at query time.
"""
from __future__ import annotations

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


@lru_cache(maxsize=4)
def get_embedder(model_name: str = DEFAULT_MODEL) -> Embedder:
    """Return a cached, warm embedder singleton so only the first call pays the
    model load (cold start)."""
    return Embedder(model_name)
