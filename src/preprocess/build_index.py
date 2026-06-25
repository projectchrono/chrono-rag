r"""Build the v2 Chrono RAG index.

Walks a Chrono checkout, chunks it structurally (AST for Python, tree-sitter for
C++), tags each chunk with PyChrono binding info, embeds with the local ONNX
embedder, and writes the index artifact (embeddings.npy + meta.jsonl +
manifest.json).

Run:
  python src/preprocess/build_index.py
Env:
  CHRONO_RAG_REPO         path to the Chrono checkout (default: chrono-oracle's clone)
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

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from core import config
from core.embedder import DEFAULT_MODEL, get_embedder
from preprocess.bindings import build_binding_map
from preprocess.chunkers import chunk_file

CHUNKER_VERSION = "v2-structural-1"
MAX_FILE_BYTES = 1_000_000

_EXTS = {".h", ".hpp", ".hxx", ".cpp", ".cc", ".cxx", ".c", ".cu", ".cuh",
         ".py", ".cs", ".md", ".rst", ".txt"}
_EXTRA_NAMES = {"CMakeLists.txt", "README", "AGENTS.md", "CHANGELOG.md", "PLATFORMS.md"}
_SKIP_DIRS = {".git", "chrono_thirdparty", "data", "images"}
_SKIP_SUBSTR = ("_generated.h", ".yy.cpp", ".tab.c")


def _default_repo() -> str:
    return os.environ.get("CHRONO_RAG_REPO", r"C:\Users\dn\Documents\chrono-oracle\repo")


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
    repo = _default_repo()
    out = os.environ.get("CHRONO_RAG_INDEX") or config.index_dir()
    model_name = os.environ.get("CHRONO_RAG_EMBED_MODEL", DEFAULT_MODEL)
    os.makedirs(out, exist_ok=True)

    print(f"[build] repo={repo}")
    print(f"[build] out={out}")
    print(f"[build] model={model_name}")
    t0 = time.time()

    bindings = build_binding_map(repo)
    print(f"[build] binding map: {len(bindings.exposed_headers)} exposed C++ headers")

    files = list(_iter_files(repo))
    print(f"[build] {len(files)} files to chunk")

    meta = []
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except OSError:
            continue
        rel = os.path.relpath(fpath, repo).replace("\\", "/")
        for ch in chunk_file(content, rel):
            if ch["language"] in ("cpp", "c"):
                exposed, module = bindings.lookup(rel)
                ch["python_exposed"] = exposed
                ch["pychrono_module"] = module
            elif ch["language"] == "py":
                ch["python_exposed"] = True
                ch["pychrono_module"] = "pychrono"
            meta.append(ch)

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

    manifest = {
        "model": model_name,
        "dim": int(emb.shape[1]),
        "n_chunks": int(emb.shape[0]),
        "n_files": len(files),
        "chunker_version": CHUNKER_VERSION,
        "index_format": 2,
        "commit": _repo_commit(repo),
        "chrono_version": _chrono_version(repo),
        "version_label": config.VERSION_LABEL,
        "built_by": "chrono-rag v2",
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"[build] DONE: {emb.shape[0]} chunks, dim {emb.shape[1]}, "
          f"{len(files)} files, {time.time() - t0:.0f}s")
    print(f"[build] manifest: {json.dumps(manifest)}")


if __name__ == "__main__":
    main()
