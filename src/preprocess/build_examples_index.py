r"""Build a standalone index for pychrono-examples-10.0.

Creates (or overwrites) its own index directory with embeddings.npy,
meta.jsonl, and manifest.json. Does NOT touch the main Chrono index.

Run build_forum_index.py on the same output directory afterward to add
forum posts to the same supplemental index.

Usage:
  python src/preprocess/build_examples_index.py [examples_dir] [out_dir]

Defaults:
  examples_dir  <repo>/../pychrono-examples-10.0
  out_dir       <repo>/index-forum

Env:
  CHRONO_RAG_EMBED_MODEL   embedding model (default: BAAI/bge-small-en-v1.5)
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from core.embedder import DEFAULT_MODEL, get_embedder
from preprocess.chunkers import chunk_file

_EXTS = {".py", ".md", ".rst", ".txt"}
_SKIP_DIRS = {".git", "__pycache__", "DEMO_OUTPUT"}


def _iter_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in _EXTS:
                yield os.path.join(dirpath, fn)


def main() -> None:
    repo_root = os.path.normpath(os.path.join(_SRC, os.pardir))
    default_examples = os.path.join(repo_root, os.pardir, "pychrono-examples-10.0")
    examples_dir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else default_examples)
    out_dir = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else os.path.join(repo_root, "index-forum"))
    model_name = os.environ.get("CHRONO_RAG_EMBED_MODEL", DEFAULT_MODEL)

    print(f"[examples] src={examples_dir}")
    print(f"[examples] out={out_dir}")
    print(f"[examples] model={model_name}")
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()

    files = list(_iter_files(examples_dir))
    print(f"[examples] {len(files)} files to chunk")

    meta = []
    for fpath in files:
        rel = os.path.relpath(fpath, examples_dir).replace("\\", "/")
        try:
            content = open(fpath, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for ch in chunk_file(content, "pychrono-examples-10.0/" + rel):
            ch["source"] = "pychrono-examples-10.0"
            meta.append(ch)

    print(f"[examples] {len(meta)} chunks; embedding ...")
    embedder = get_embedder(model_name)
    texts = [m["text"] for m in meta]

    batch = 256
    vecs = []
    for i in range(0, len(texts), batch):
        vecs.append(embedder.embed_documents(texts[i:i + batch]))
        print(f"[examples]   {min(i + batch, len(texts))}/{len(texts)}")
    emb = np.vstack(vecs).astype(np.float32) if vecs else np.zeros((0, embedder.dim), np.float32)

    np.save(os.path.join(out_dir, "embeddings.npy"), emb)
    with open(os.path.join(out_dir, "meta.jsonl"), "w", encoding="utf-8") as fh:
        for m in meta:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")

    dim = int(emb.shape[1]) if emb.shape[0] > 0 else embedder.dim
    manifest = {
        "model": model_name,
        "dim": dim,
        "n_chunks": int(emb.shape[0]),
        "examples_files": len(files),
        "examples_chunks": len(meta),
        "index_format": 2,
        "built_by": "chrono-rag build_examples_index",
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"[examples] DONE: {emb.shape[0]} chunks, {len(files)} files, "
          f"{time.time() - t0:.0f}s → {out_dir}")


if __name__ == "__main__":
    main()
