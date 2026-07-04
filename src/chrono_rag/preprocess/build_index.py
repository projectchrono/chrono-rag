r"""Build the main Chrono RAG index.

Walks a Chrono checkout, chunks it structurally (AST for Python, tree-sitter for
C++), embeds with the local ONNX embedder, and writes the index artifact
(embeddings.npy + meta.jsonl + manifest.json).

Run (from the repo root):
  CHRONO_RAG_REPO=/path/to/chrono python -m chrono_rag.preprocess.build_index
Env:
  CHRONO_RAG_REPO         path to the Chrono checkout (required)
  CHRONO_RAG_INDEX        output index dir (default: <repo_root>/index)
  CHRONO_RAG_EMBED_MODEL  embedder (default: BAAI/bge-small-en-v1.5)
  CHRONO_RAG_VERSION      Chrono version label (default: parsed, else 10.0)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

import numpy as np

from chrono_rag.core import config
from chrono_rag.core.embedder import DEFAULT_MODEL, get_embedder
from chrono_rag.preprocess.chunkers import chunk_file

CHUNKER_VERSION = "v2-structural-1"
MAX_FILE_BYTES = 1_000_000

_EXTS = {".h", ".hpp", ".hxx", ".cpp", ".cc", ".cxx", ".c", ".cu", ".cuh",
         ".py", ".cs", ".md", ".rst", ".txt"}
_EXTRA_NAMES = {"CMakeLists.txt", "README", "AGENTS.md", "CHANGELOG.md", "PLATFORMS.md"}
_SKIP_DIRS = {".git", "chrono_thirdparty", "data", "images"}
_SKIP_SUBSTR = ("_generated.h", ".yy.cpp", ".tab.c")


def _repo_or_die() -> str:
    """Resolve the Chrono checkout to index, or exit with clear guidance."""
    repo = os.environ.get("CHRONO_RAG_REPO") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not repo:
        print("error: no Chrono checkout given. Set CHRONO_RAG_REPO to your clone of "
              "https://github.com/projectchrono/chrono (or pass it as the first argument).",
              file=sys.stderr)
        raise SystemExit(2)
    repo = os.path.abspath(repo)
    if not os.path.isdir(repo):
        print(f"error: CHRONO_RAG_REPO points at {repo!r}, which is not a directory.",
              file=sys.stderr)
        raise SystemExit(2)
    return repo


def _repo_commit(repo: str) -> str:
    try:
        out = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _chrono_version(repo: str) -> str:
    env = os.environ.get("CHRONO_RAG_VERSION")
    if env:
        return env
    cml = os.path.join(repo, "CMakeLists.txt")
    try:
        with open(cml, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
        m = re.search(r"project\s*\(\s*Chrono[^\)]*VERSION\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.I)
        if m:
            return m.group(1)
    except OSError:
        pass
    return "10.0"


def _version_label(version: str) -> str:
    """'10.0.1' -> 'PyChrono 10.0' (the user-facing scope label)."""
    major_minor = ".".join(version.split(".")[:2])
    return f"PyChrono {major_minor}"


def _want(path: str) -> bool:
    base = os.path.basename(path)
    if any(s in base for s in _SKIP_SUBSTR):
        return False
    if os.path.splitext(base)[1].lower() in _EXTS or base in _EXTRA_NAMES:
        try:
            return os.path.getsize(path) <= MAX_FILE_BYTES
        except OSError:
            return False
    return False


def _iter_files(repo: str):
    for dirpath, dirnames, filenames in os.walk(repo):
        rel = os.path.relpath(dirpath, repo).replace("\\", "/")
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        if any(part in _SKIP_DIRS for part in rel.split("/")):
            continue
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            if _want(full):
                yield full


def main() -> None:
    repo = _repo_or_die()
    out = os.environ.get("CHRONO_RAG_INDEX") or config.index_dir()
    model_name = os.environ.get("CHRONO_RAG_EMBED_MODEL", DEFAULT_MODEL)
    os.makedirs(out, exist_ok=True)

    print(f"[build] repo={repo}")
    print(f"[build] out={out}")
    print(f"[build] model={model_name}")
    t0 = time.time()

    files = list(_iter_files(repo))
    print(f"[build] {len(files)} files to chunk")
    if not files:
        print(f"error: found no source files under {repo!r}. Is CHRONO_RAG_REPO "
              "pointing at a Chrono checkout?", file=sys.stderr)
        raise SystemExit(2)

    meta = []
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except OSError:
            continue
        rel = os.path.relpath(fpath, repo).replace("\\", "/")
        meta.extend(chunk_file(content, rel))

    print(f"[build] {len(meta)} chunks; embedding with {model_name} ...")
    embedder = get_embedder(model_name)
    texts = [m["text"] for m in meta]

    batch = 256
    vecs = []
    for i in range(0, len(texts), batch):
        vecs.append(embedder.embed_documents(texts[i:i + batch]))
        if (i // batch) % 20 == 0:
            print(f"[build]   embedded {min(i + batch, len(texts))}/{len(texts)}")
    emb = np.vstack(vecs).astype(np.float32)

    np.save(os.path.join(out, "embeddings.npy"), emb)
    with open(os.path.join(out, "meta.jsonl"), "w", encoding="utf-8") as fh:
        for m in meta:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")

    version = _chrono_version(repo)
    manifest = {
        "model": model_name,
        "dim": int(emb.shape[1]),
        "n_chunks": int(emb.shape[0]),
        "n_files": len(files),
        "chunker_version": CHUNKER_VERSION,
        "index_format": 2,
        "commit": _repo_commit(repo),
        "chrono_version": version,
        "version_label": _version_label(version),
        "built_by": "chrono-rag",
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"[build] DONE: {emb.shape[0]} chunks, dim {emb.shape[1]}, "
          f"{len(files)} files, {time.time() - t0:.0f}s")
    print(f"[build] manifest: {json.dumps(manifest)}")


if __name__ == "__main__":
    main()
