"""chrono-rag: local retrieval assistant for Project Chrono / PyChrono.

Layout:
  core/        retrieval (store, embedder, bm25, fusion) - no server or LLM deps
  inference/   the BYOK LLM wrapper used by the answer path
  surfaces/    thin adapters: CLI, MCP server, shared formatting/answer logic
  webapp       FastAPI backend for the React frontend
  preprocess/  index builders (main, examples, forum)
  eval/        retrieval-quality harness + gold set
"""

__version__ = "0.9.0"
