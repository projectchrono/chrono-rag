r"""Chrono RAG v2 - MCP server.

Exposes the local hybrid retrieval core as MCP tools so any MCP-aware editor
(Cursor, Claude Code, Windsurf, VS Code Copilot agent, ...) can search Chrono.
Tool signatures match the chrono-oracle prototype (`search_chrono`,
`chrono_digest`) so existing editor configs keep working.

Run (stdio):
  python src/surfaces/mcp_server.py
  (or: python -m surfaces.mcp_server  with src on PYTHONPATH)
"""
from __future__ import annotations

import os
import sys

# bge-small ONNX is cached locally after first run; stay offline for fast startup.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

# Bootstrap: put src/ on the path so `python <this file>` works without PYTHONPATH.
_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcp.server.fastmcp import FastMCP

from surfaces.format import render_digest, render_results

mcp = FastMCP("chrono-rag")


@mcp.tool()
def search_chrono(query: str, k: int = 8, full: bool = False) -> str:
    """Semantically search the Project Chrono / PyChrono source, docs, and demos.

    Returns the top-k most relevant chunks, each with file path + line number, a
    relevance score, and a snippet. Use this for pinpoint "where is X / how does
    Y work / how do I do Z in PyChrono" questions over the real Chrono codebase.

    Args:
        query: Natural-language question (e.g. "attach a lidar to a vehicle").
        k: Number of results to return (default 8, max 25).
        full: If true, return the full chunk text instead of a 500-char snippet.
    """
    return render_results(query, k=k, full=full)


@mcp.tool()
def chrono_digest(section: str = "") -> str:
    """Read the curated Chrono architecture digest (the human-readable "map").

    With no argument, returns the list of section headings so you can pick one.
    Pass a section name (case-insensitive substring of a heading) to get just that
    section. Use this for orientation / "what modules exist" questions; use
    search_chrono for exact code.

    Args:
        section: Substring of a section heading to retrieve. Empty = list headings.
    """
    return render_digest(section)


if __name__ == "__main__":
    mcp.run()
