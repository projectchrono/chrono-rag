"""
Entry point for indexing (prompt, code) example pairs into MongoDB.

To add more pairs, append to PAIRS below.
Paths in PAIRS are relative to this file's directory (src/preprocess/).
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from preprocess.dataparser import parse_example_pairs
from preprocess.embeddings import generate_embeddings
from preprocess.vectorstore import create_vector_search_index, upsert_documents

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

PAIRS = [
    (
        os.path.join(_REPO_ROOT, "../../example/input1.txt"),
        os.path.join(_REPO_ROOT, "../../example/cleaned_truth1.py"),
    ),
]


def main() -> None:
    print("Parsing example pairs...")
    documents = parse_example_pairs(PAIRS)
    print(f"  → {len(documents)} document(s)")

    print("Generating embeddings...")
    documents = generate_embeddings(documents)
    print(f"  → embeddings attached to {len(documents)} document(s)")

    print("Upserting to MongoDB...")
    upsert_documents(documents)
    print("  → upsert complete")

    print("Creating vector search index...")
    try:
        create_vector_search_index()
        print("  → index created")
    except Exception as exc:
        print(f"  → index may already exist ({exc})")

    print("Done.")


if __name__ == "__main__":
    main()
