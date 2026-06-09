"""
Upserts Document objects (with embeddings) into a local MongoDB Atlas instance
and creates an Atlas Vector Search index on the embedding field.

Requires the mongodb/mongodb-atlas-local Docker container:
    docker run -d -p 27017:27017 --name chrono-mongo mongodb/mongodb-atlas-local
"""
from __future__ import annotations

from typing import List

from pymongo import MongoClient

from src.preprocess.dataparser import Document

_MONGO_URI = "mongodb://localhost:27017"
_DB_NAME = "chrono_rag"
_COLLECTION_NAME = "chunks"


def _get_collection():
    client = MongoClient(_MONGO_URI)
    return client[_DB_NAME][_COLLECTION_NAME]


def upsert_documents(documents: List[Document]) -> None:
    collection = _get_collection()
    for doc in documents:
        collection.update_one(
            {"file_path": doc.file_path, "chunk_name": doc.chunk_name, "chunk_type": doc.chunk_type},
            {"$set": {
                "source_repo": doc.source_repo,
                "file_path": doc.file_path,
                "language": doc.language,
                "chunk_type": doc.chunk_type,
                "chunk_name": doc.chunk_name,
                "content": doc.content,
                "answer": doc.answer,
                "embedding": doc.embedding,
            }},
            upsert=True,
        )


def create_vector_search_index() -> None:
    collection = _get_collection()
    collection.database.command({
        "createSearchIndexes": _COLLECTION_NAME,
        "indexes": [{
            "name": "vector_index",
            "type": "vectorSearch",
            "definition": {
                "fields": [{
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": 1536,
                    "similarity": "cosine",
                }]
            },
        }],
    })