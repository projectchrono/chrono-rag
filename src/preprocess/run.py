"""
Pipeline entry point. Runs the full preprocessing pipeline:
  1. Clone repos (skips if already present)
  2. Parse and chunk source files
  3. Generate embeddings
  4. Upsert into MongoDB
  5. Create vector search index
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from preprocess.dataparser import parse_repos
from preprocess.embeddings import generate_embeddings
from preprocess.vectorstore import create_vector_search_index, upsert_documents

_REPOS_DIR = os.getenv(
    "REPOS_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../repos"),
)


def main() -> None:
    print("Parsing repos...")
    documents = list(parse_repos(_REPOS_DIR))
    print(f"  → {len(documents)} chunks found")

    print("Generating embeddings...")
    documents = generate_embeddings(documents)
    print(f"  → embeddings attached to {len(documents)} documents")

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
