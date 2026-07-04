"""Surface-agnostic retrieval core for Chrono RAG v2.

This package holds everything below the surfaces (MCP / CLI / web): the local
embedder, the in-memory NumPy vector store, the BM25 lexical index, and the
hybrid retrieval logic (fusion + abstention + injection filter). No surface,
MongoDB, or server-side-generation assumptions live here.
"""
