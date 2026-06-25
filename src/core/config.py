"""Core configuration: index location and the user-facing version boundary."""
from __future__ import annotations

import os

# Surfaced to users as the honest scope boundary (Phase 1 is single-version, 10.0 only).
VERSION_LABEL = "PyChrono 10.0"

# Tunable retrieval constants. These are PLACEHOLDERS pending calibration by the
# eval harness (the whole reason the harness is a first-class Phase 1 deliverable).
DENSE_FLOOR = 0.62          # cosine below which a result is weak (bge-small scale; eval-calibrated)
MARGIN_FLOOR = 0.03         # top1-top2 dense margin below which the top match is ambiguous
RRF_K = 60                  # reciprocal-rank-fusion damping constant
PYCHRONO_BOOST = 0.15       # extra fused weight for Python/PyChrono chunks on Python queries


def _repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, os.pardir, os.pardir))


def index_dir() -> str:
    """Directory holding embeddings.npy, meta.jsonl, and manifest.json.

    Override with the CHRONO_RAG_INDEX env var; otherwise defaults to an
    `index/` directory at the repo root (sibling of `src/`).
    """
    env = os.getenv("CHRONO_RAG_INDEX")
    if env:
        return os.path.abspath(env)
    return os.path.join(_repo_root(), "index")


def digest_path() -> str:
    """Path to the curated architecture digest served by chrono_digest.

    Override with CHRONO_RAG_DIGEST; otherwise defaults to docs/chrono-digest.md
    at the repo root.
    """
    env = os.getenv("CHRONO_RAG_DIGEST")
    if env:
        return os.path.abspath(env)
    return os.path.join(_repo_root(), "docs", "chrono-digest.md")
