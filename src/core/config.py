"""Core configuration: index location and the user-facing version boundary."""
from __future__ import annotations

import os
from typing import Optional

# Surfaced to users as the honest scope boundary (Phase 1 is single-version, 10.0 only).
VERSION_LABEL = "PyChrono 10.0"

# Tunable retrieval constants. These are PLACEHOLDERS pending calibration by the
# eval harness (the whole reason the harness is a first-class Phase 1 deliverable).
DENSE_FLOOR = 0.62          # cosine below which a result is weak (bge-small scale; eval-calibrated)
RRF_K = 60                  # reciprocal-rank-fusion damping constant
PYCHRONO_BOOST = 0.15       # extra fused weight for Python/PyChrono chunks on Python queries
FORUM_PENALTY = 0.005       # slight fused-score penalty for forum chunks; code/docs win close calls
                            # (RRF scores are ~0.02-0.05; keep this well below one rank step, 1/RRF_K)


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


# --- LLM backend (BYOK answer path) -----------------------------------------
# The `ask` / web answer path is backend-agnostic: cloud (Anthropic, OpenAI) or
# any OpenAI-compatible local server, e.g. AMD Lemonade at
# http://localhost:13305/v1. These read the CHRONO_RAG_LLM_* env vars; the LLM
# wrapper layers explicit args and per-provider defaults on top.

def llm_provider() -> Optional[str]:
    """Explicit provider from CHRONO_RAG_LLM_PROVIDER, or None to auto-resolve.

    One of `anthropic`, `openai`, `local`. When unset the LLM wrapper infers a
    provider (base URL -> local, model name -> cloud, key present -> anthropic).
    """
    v = os.getenv("CHRONO_RAG_LLM_PROVIDER")
    return v.strip().lower() if v else None


def llm_base_url() -> Optional[str]:
    """OpenAI-compatible base URL for a local server (CHRONO_RAG_LLM_BASE_URL)."""
    v = os.getenv("CHRONO_RAG_LLM_BASE_URL")
    return v.strip() if v else None


def llm_model() -> Optional[str]:
    """Model id from CHRONO_RAG_LLM_MODEL, or None to use the provider default."""
    v = os.getenv("CHRONO_RAG_LLM_MODEL")
    return v.strip() if v else None


def llm_api_key() -> Optional[str]:
    """Explicit key from CHRONO_RAG_LLM_API_KEY (a dummy is fine for local)."""
    v = os.getenv("CHRONO_RAG_LLM_API_KEY")
    return v.strip() if v else None


def extra_index_dirs() -> list[str]:
    """Additional index directories from CHRONO_RAG_EXTRA_INDEX.

    Multiple directories are separated by os.pathsep (';' on Windows, ':' on
    Unix); splitting on a bare ':' would shatter a Windows absolute path at its
    drive-letter colon. Set this to point at supplemental indexes (examples,
    forum, etc.) that are loaded alongside the main CHRONO_RAG_INDEX at query time.
    """
    v = os.getenv("CHRONO_RAG_EXTRA_INDEX")
    if not v:
        return []
    return [os.path.abspath(p.strip()) for p in v.split(os.pathsep) if p.strip()]
