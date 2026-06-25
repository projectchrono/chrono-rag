r"""Chrono RAG v2 - command-line surface.

Two subcommands over the shared retrieval core:
  search  - print the top retrieved Chrono/PyChrono chunks (no LLM, no key).
  ask     - BYOK: retrieve, then have an LLM answer from the retrieved context.

Run:
  python src/surfaces/cli.py search "how do I attach a lidar in pychrono"
  python src/surfaces/cli.py ask    "create a rigid body box in pychrono"
"""
from __future__ import annotations

import argparse
import os
import sys

# Bootstrap src/ onto the path so direct invocation works without PYTHONPATH.
_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from surfaces.format import render_results  # noqa: E402


def _cmd_search(query: str, k: int, full: bool) -> int:
    print(render_results(query, k=k, full=full))
    return 0


def _cmd_ask(query: str, k: int, model: str | None) -> int:
    try:
        from surfaces.answer import answer as run_answer
        res = run_answer(query, k=k, model=model)
    except ImportError:
        print(
            "The 'ask' command needs an LLM SDK (anthropic and/or openai) and an "
            "API key. Install one (`pip install anthropic`) and set ANTHROPIC_API_KEY "
            "or OPENAI_API_KEY. Meanwhile, `search` works with no key.",
            file=sys.stderr,
        )
        return 1

    print(res["answer"])
    if res["sources"]:
        print("\n[sources] " + ", ".join(res["sources"]))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="chrono-rag",
        description="Local Chrono/PyChrono retrieval assistant (targets PyChrono 10.0).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("search", help="retrieve relevant Chrono chunks (no LLM)")
    ps.add_argument("query", nargs="+", help="natural-language question")
    ps.add_argument("-k", type=int, default=8, help="number of results (default 8)")
    ps.add_argument("--full", action="store_true", help="print full chunks, not snippets")

    pa = sub.add_parser("ask", help="retrieve + LLM answer (bring your own key)")
    pa.add_argument("query", nargs="+", help="natural-language question")
    pa.add_argument("-k", type=int, default=8, help="chunks of context (default 8)")
    pa.add_argument("--model", default=None, help="LLM model id (default: provider default)")

    args = p.parse_args(argv)
    query = " ".join(args.query)
    if args.cmd == "search":
        return _cmd_search(query, args.k, args.full)
    if args.cmd == "ask":
        return _cmd_ask(query, args.k, args.model)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
