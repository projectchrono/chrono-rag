"""
Generates embeddings for Document objects using OpenAI text-embedding-3-small.
"""
from __future__ import annotations

from typing import List

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

from src.preprocess.dataparser import Document

load_dotenv()


def generate_embeddings(documents: List[Document], batch_size: int = 100) -> List[Document]:
    embedder = OpenAIEmbeddings(model="text-embedding-3-small")

    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        vectors = embedder.embed_documents([doc.content for doc in batch])
        for doc, vec in zip(batch, vectors):
            doc.embedding = vec

    return documents
