r"""Append verified pychrono-examples-10.0 to the existing index (incremental).

Reads the verify report, chunks each verified (pass / pass_timeout) example,
embeds with the index's own model, and appends to embeddings.npy + meta.jsonl.
Idempotent: existing `examples/*` rows are dropped and re-added on each run, so
the full Chrono index does not need rebuilding.

Usage:
  python src/preprocess/index_examples.py <examples_dir> <verify_report.json>
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from core import config
from core.embedder import get_embedder
from core.store import load_store
from preprocess.chunkers import chunk_file

VERIFIED = {"pass", "pass_timeout"}


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: index_examples.py <examples_dir> <verify_report.json>", file=sys.stderr)
        raise SystemExit(2)
    examples_dir, report_path = sys.argv[1], sys.argv[2]
    index_dir = os.environ.get("CHRONO_RAG_INDEX") or config.index_dir()

    store = load_store(index_dir)
    model = store.model_name
    print(f"[examples] index={index_dir} ({len(store)} chunks, model={model})")

    report = json.load(open(report_path, encoding="utf-8"))
    verified = [r["file"] for r in report if r.get("status") in VERIFIED]
    print(f"[examples] {len(verified)} verified examples to index")

    # Drop any prior examples/* rows (idempotent re-runs).
    keep = [i for i, m in enumerate(store.meta) if not str(m.get("path", "")).startswith("examples/")]
    base_emb = store.embeddings[keep]
    base_meta = [store.meta[i] for i in keep]

    new_meta = []
    for rel in verified:
        fp = os.path.join(examples_dir, rel.replace("/", os.sep))
        try:
            content = open(fp, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for ch in chunk_file(content, "examples/" + rel):
            ch["source"] = "pychrono-examples-10.0"
            ch["verified"] = True
            new_meta.append(ch)

    print(f"[examples] {len(new_meta)} chunks from verified examples; embedding ...")
    embedder = get_embedder(model)
    new_vecs = embedder.embed_documents([m["text"] for m in new_meta]) if new_meta else np.zeros((0, base_emb.shape[1]), np.float32)

    emb = np.vstack([base_emb, new_vecs]).astype(np.float32)
    meta = base_meta + new_meta

    np.save(os.path.join(index_dir, "embeddings.npy"), emb)
    with open(os.path.join(index_dir, "meta.jsonl"), "w", encoding="utf-8") as fh:
        for m in meta:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")

    man_path = os.path.join(index_dir, "manifest.json")
    manifest = json.load(open(man_path, encoding="utf-8")) if os.path.exists(man_path) else {}
    manifest["n_chunks"] = int(emb.shape[0])
    manifest["examples_chunks"] = len(new_meta)
    manifest["examples_files"] = len(verified)
    json.dump(manifest, open(man_path, "w", encoding="utf-8"), indent=2)

    print(f"[examples] DONE: index now {emb.shape[0]} chunks (+{len(new_meta)} example chunks)")


if __name__ == "__main__":
    main()
