"""Merge the outputs of sharded index builds into one index.

A GitHub-hosted runner needs many hours to embed the whole Chrono corpus in one
job, so the publish workflow runs N jobs with CHRONO_RAG_SHARD=i/N (each chunks
the same checkout and embeds one contiguous slice) and then merges them here.

Run:
  python -m chrono_rag.preprocess.merge_shards <out_dir> <shard_dir> [<shard_dir> ...]

Every shard must come from the same commit and model and declare the same
shard count and total; the result is byte-for-byte the index a single full
build would have written (same chunk order, same manifest minus `shard`).
"""
from __future__ import annotations

import json
import os
import shutil
import sys

import numpy as np

_MUST_MATCH = ("model", "dim", "commit", "chunker_version", "index_format")


def _read_manifest(d: str) -> dict:
    with open(os.path.join(d, "manifest.json"), encoding="utf-8") as fh:
        return json.load(fh)


def merge(out: str, shard_dirs: list[str]) -> dict:
    """Merge `shard_dirs` (any order) into `out`; returns the merged manifest."""
    if not shard_dirs:
        raise ValueError("no shard directories given")
    shards = []
    for d in shard_dirs:
        man = _read_manifest(d)
        info = man.get("shard")
        if not info:
            raise ValueError(f"{d}: manifest has no 'shard' entry (not a shard build)")
        shards.append((int(info["index"]), int(info["of"]), int(info["total_chunks"]), d, man))
    shards.sort(key=lambda s: s[0])

    n = shards[0][1]
    total = shards[0][2]
    if [s[0] for s in shards] != list(range(n)):
        raise ValueError(f"incomplete shard set: have indexes {[s[0] for s in shards]}, need 0..{n - 1}")
    if any(s[1] != n or s[2] != total for s in shards):
        raise ValueError("shards disagree on shard count or total chunk count")
    first = shards[0][4]
    for _, _, _, d, man in shards[1:]:
        for key in _MUST_MATCH:
            if man.get(key) != first.get(key):
                raise ValueError(f"{d}: manifest '{key}' differs from shard 0 "
                                 f"({man.get(key)!r} vs {first.get(key)!r})")

    os.makedirs(out, exist_ok=True)
    embs = [np.load(os.path.join(d, "embeddings.npy")) for *_, d, _ in shards]
    emb = np.vstack(embs).astype(np.float32)
    if emb.shape[0] != total:
        raise ValueError(f"merged {emb.shape[0]} chunks, manifests promised {total}")
    np.save(os.path.join(out, "embeddings.npy"), emb)

    n_meta = 0
    with open(os.path.join(out, "meta.jsonl"), "w", encoding="utf-8") as dst:
        for *_, d, _ in shards:
            with open(os.path.join(d, "meta.jsonl"), encoding="utf-8") as src:
                for line in src:
                    if line.strip():
                        dst.write(line if line.endswith("\n") else line + "\n")
                        n_meta += 1
    if n_meta != total:
        raise ValueError(f"merged {n_meta} meta rows, manifests promised {total}")

    manifest = dict(first)
    manifest.pop("shard", None)
    manifest["n_chunks"] = int(emb.shape[0])
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    out, shard_dirs = args[0], args[1:]
    if os.path.isdir(out) and os.listdir(out):
        shutil.rmtree(out)
    manifest = merge(out, shard_dirs)
    print(f"[merge] {manifest['n_chunks']} chunks from {len(shard_dirs)} shards -> {out}")
    print(f"[merge] manifest: {json.dumps(manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
