"""Core configuration: index location and the user-facing version boundary."""
from __future__ import annotations

import os
from typing import Optional

# GitHub repo that hosts the code and the prebuilt-index release assets.
# `chrono-rag get-index` downloads from this repo's Releases page. Single place
# to update if the repository moves to another organization.
GITHUB_REPO = "projectchrono/chrono-rag"

# Fallback user-facing scope label; the index manifest's `version_label`
# (written at build time from the indexed Chrono checkout) takes precedence.
VERSION_LABEL = "PyChrono 10.0"

# Tunable retrieval constants, validated against the eval harness
# (chrono_rag.eval.run_eval on the 10.0 index: recall@8 0.93, MRR 0.72, all
# negatives abstain, no false abstentions). Re-run the harness when changing
# any of these or rebuilding against a new Chrono version.
DENSE_FLOOR = 0.62          # cosine below which a result is weak (bge-small scale). The
                            # harness's floor sweep shows clean positive/negative separation
                            # from 0.62 to 0.76; 0.62 is the conservative end of that plateau.
RRF_K = 60                  # reciprocal-rank-fusion damping constant (standard default)
PYCHRONO_BOOST = 0.15       # extra fused weight for Python/PyChrono chunks on Python queries
FORUM_PENALTY = 0.005       # slight fused-score penalty for forum chunks; code/docs win close calls
                            # (RRF scores are ~0.02-0.05; keep this well below one rank step, 1/RRF_K)


def _repo_root() -> Optional[str]:
    """Root of a source checkout when running from one (editable install),
    else None (e.g. installed as a wheel into site-packages)."""
    # config.py lives at <root>/src/chrono_rag/core/config.py
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.normpath(os.path.join(here, os.pardir, os.pardir, os.pardir))
    if os.path.exists(os.path.join(root, "pyproject.toml")):
        return root
    return None


def index_dir() -> str:
    """Directory holding embeddings.npy, meta.jsonl, and manifest.json.

    Override with the CHRONO_RAG_INDEX env var; otherwise defaults to `index/`
    at the repo root when running from a source checkout, else `index/` under
    the current working directory.
    """
    env = os.getenv("CHRONO_RAG_INDEX")
    if env:
        return os.path.abspath(env)
    root = _repo_root()
    return os.path.join(root, "index") if root else os.path.abspath("index")


def digest_path() -> str:
    """Path to the curated architecture digest served by chrono_digest.

    Override with CHRONO_RAG_DIGEST; otherwise defaults to docs/chrono-digest.md
    at the repo root.
    """
    env = os.getenv("CHRONO_RAG_DIGEST")
    if env:
        return os.path.abspath(env)
    root = _repo_root()
    base = root if root else os.getcwd()
    return os.path.join(base, "docs", "chrono-digest.md")


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
