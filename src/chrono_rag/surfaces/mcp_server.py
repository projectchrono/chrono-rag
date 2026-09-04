r"""Chrono RAG - MCP server.

Exposes the local hybrid retrieval core as MCP tools so any MCP-aware editor
(Cursor, Claude Code, Windsurf, VS Code Copilot agent, ...) can search Chrono.

Run (stdio):
  chrono-rag-mcp
  (or: python -m chrono_rag.surfaces.mcp_server)

The first query downloads the small embedding model once; after that everything
is local. To force fully-offline startup on a machine where the model is already
cached, set HF_HUB_OFFLINE=1 in the server's environment. (It is deliberately
NOT forced here: forcing it used to break the very first run, before the model
was cached.)
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from chrono_rag.surfaces.format import render_digest, render_results

mcp = MCPServer("chrono-rag")


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


def main() -> None:
    """Console-script entry point (`chrono-rag-mcp`)."""
    mcp.run()


if __name__ == "__main__":
    main()
