#!/usr/bin/env python3
"""Convert a MongoDB BSON dump to v2's NumPy index format.

The main branch stored embeddings in MongoDB (OpenAI text-embedding-3-small, 1536-dim).
This script converts that dump to the three-file index format used by v2's VectorStore:
  embeddings.npy   — (N, 1536) float32, L2-normalized
  meta.jsonl       — one JSON object per line, aligned by row
  manifest.json    — model name, dim, provenance

Usage:
  # from a zip (the file as committed on main)
  python scripts/convert_mongo_index.py --zip chrono_embeddings.zip --out index-mongo/

  # from an already-extracted BSON file
  python scripts/convert_mongo_index.py --bson chrono_dump/chrono_rag/chunks.bson --out index-mongo/
"""
from __future__ import annotations

import argparse
import io
import json
import os
import zipfile

import numpy as np

MODEL_NAME = "text-embedding-3-small"
DIM = 1536


def _l2_normalize(arr: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (arr / norms).astype(np.float32)


def _ext_language(file_path: str) -> str:
    ext = os.path.splitext(file_path)[-1].lstrip(".").lower()
    return {"py": "py", "cpp": "cpp", "h": "cpp", "hpp": "cpp", "txt": "text", "json": "json"}.get(ext, ext)


def _load_bson_bytes(data: bytes) -> list[dict]:
    try:
        import bson
    except ImportError as exc:
        raise ImportError(
            "pymongo (or the standalone bson package) is required to read BSON files. "
            "Install it with: pip install pymongo"
        ) from exc
    return bson.decode_all(data)


def _read_bson_from_file(path: str) -> list[dict]:
    with open(path, "rb") as fh:
        return _load_bson_bytes(fh.read())


def _read_bson_from_zip(zip_path: str) -> list[dict]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        bson_names = [n for n in zf.namelist() if n.endswith(".bson")]
        if not bson_names:
            raise ValueError(f"No .bson file found inside {zip_path}")
        if len(bson_names) > 1:
            # prefer the chunks collection
            candidates = [n for n in bson_names if "chunks" in n]
            bson_names = candidates or bson_names
        name = bson_names[0]
        print(f"Reading {name} from zip …")
        data = zf.read(name)
    return _load_bson_bytes(data)


def convert(docs: list[dict], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)

    embeddings = []
    meta_rows = []

    for doc in docs:
        emb = doc.get("embedding")
        if not emb:
            continue

        content = doc.get("content", "")
        answer = doc.get("answer", "")
        text = f"{answer}\n{content}".strip() if answer else content

        file_path = doc.get("file_path", "")
        language = doc.get("language") or _ext_language(file_path)

        meta_rows.append({
            "text": text,
            "path": file_path,
            "line": 0,
            "symbol": doc.get("chunk_name", ""),
            "language": language,
            "chunk_type": doc.get("chunk_type", ""),
        })
        embeddings.append(emb)

    arr = _l2_normalize(np.array(embeddings, dtype=np.float32))

    emb_path = os.path.join(out_dir, "embeddings.npy")
    meta_path = os.path.join(out_dir, "meta.jsonl")
    man_path = os.path.join(out_dir, "manifest.json")

    np.save(emb_path, arr)
    print(f"Saved {emb_path}  shape={arr.shape}")

    with open(meta_path, "w", encoding="utf-8") as fh:
        for row in meta_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Saved {meta_path}  rows={len(meta_rows)}")

    manifest = {"model": MODEL_NAME, "dim": DIM, "source": "mongo-dump", "n_chunks": len(meta_rows)}
    with open(man_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"Saved {man_path}")

    print(f"\nDone. Switch to this index with:")
    print(f"  CHRONO_RAG_INDEX={os.path.abspath(out_dir)} python src/surfaces/cli.py search \"<query>\"")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert MongoDB BSON dump to v2 index format.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--zip", metavar="PATH", help="Path to chrono_embeddings.zip")
    src.add_argument("--bson", metavar="PATH", help="Path to an extracted .bson file")
    parser.add_argument("--out", default="index-mongo", metavar="DIR",
                        help="Output directory (default: index-mongo/)")
    args = parser.parse_args()

    if args.zip:
        docs = _read_bson_from_zip(args.zip)
    else:
        docs = _read_bson_from_file(args.bson)

    print(f"Loaded {len(docs)} documents")
    convert(docs, args.out)


if __name__ == "__main__":
    main()
