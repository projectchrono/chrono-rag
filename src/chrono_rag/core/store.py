"""In-memory NumPy vector store.

Loads the index artifact (embeddings.npy + meta.jsonl + manifest.json) and does
brute-force cosine search. At this corpus scale (tens of thousands of chunks,
~45-155 MB in RAM) a query is a single matmul, so there is no need for an ANN
index or an on-disk vector database.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import config


@dataclass
class VectorStore:
    embeddings: np.ndarray              # (N, dim) float32, L2-normalized
    meta: List[Dict[str, Any]]          # length N; per-chunk metadata + text
    manifest: Dict[str, Any] = field(default_factory=dict)

    @property
    def model_name(self) -> Optional[str]:
        return self.manifest.get("model")

    @property
    def dim(self) -> int:
        return int(self.embeddings.shape[1])

    def __len__(self) -> int:
        return int(self.embeddings.shape[0])

    def dense_search(self, query_vec: np.ndarray, k: int) -> List[Tuple[int, float]]:
        """Top-k by cosine (embeddings are normalized, so this is a dot product)."""
        scores = self.embeddings @ query_vec
        k = max(1, min(int(k), scores.shape[0]))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(int(i), float(scores[i])) for i in top]


def load_multi_store(dirs: List[str]) -> "VectorStore":
    """Load and concatenate multiple index directories into one VectorStore.

    All directories must have been built with the same embedding model (same
    dimension). The first directory's manifest is used as the primary one.
    """
    if not dirs:
        raise ValueError("load_multi_store requires at least one directory")
    stores = [load_store(d) for d in dirs]
    if len(stores) == 1:
        return stores[0]
    dims = {s.dim for s in stores}
    if len(dims) > 1:
        raise ValueError(
            f"Cannot merge indexes with different embedding dimensions {dims}. "
            "All indexes must be built with the same model."
        )
    emb = np.vstack([s.embeddings for s in stores]).astype(np.float32)
    meta: List[Dict[str, Any]] = []
    for s in stores:
        meta.extend(s.meta)
    manifest = stores[0].manifest.copy()
    manifest["n_chunks"] = int(emb.shape[0])
    manifest["combined_from"] = dirs
    return VectorStore(embeddings=emb, meta=meta, manifest=manifest)


def load_store(index_dir: Optional[str] = None) -> VectorStore:
    """Load and validate the index artifact from `index_dir` (or the default)."""
    d = index_dir or config.index_dir()
    emb_path = os.path.join(d, "embeddings.npy")
    meta_path = os.path.join(d, "meta.jsonl")
    if not os.path.exists(emb_path):
        raise FileNotFoundError(
            f"No index at {d!r} (missing embeddings.npy). Build or download the "
            "index first (set CHRONO_RAG_INDEX to point elsewhere)."
        )
    if not os.path.exists(meta_path):
        raise FileNotFoundError(
            f"Index at {d!r} is incomplete (embeddings.npy present but meta.jsonl "
            "missing). Re-download or rebuild it."
        )

    emb = np.load(emb_path).astype(np.float32)

    meta: List[Dict[str, Any]] = []
    with open(meta_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                meta.append(json.loads(line))

    manifest: Dict[str, Any] = {}
    man_path = os.path.join(d, "manifest.json")
    if os.path.exists(man_path):
        with open(man_path, encoding="utf-8") as fh:
            manifest = json.load(fh)

    if len(meta) != emb.shape[0]:
        raise ValueError(
            f"index corrupt: {len(meta)} meta rows != {emb.shape[0]} embedding rows"
        )
    man_dim = manifest.get("dim")
    if man_dim is not None and int(man_dim) != emb.shape[1]:
        raise ValueError(
            f"index/manifest mismatch: manifest dim {man_dim} != embeddings dim {emb.shape[1]}"
        )

    return VectorStore(embeddings=emb, meta=meta, manifest=manifest)
