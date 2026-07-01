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


def _cmd_ask(query: str, k: int, model: str | None, provider: str | None) -> int:
    try:
        from surfaces.answer import answer as run_answer
        res = run_answer(query, k=k, model=model, provider=provider)
    except ImportError:
        print(
            "The 'ask' command needs an LLM SDK. For a cloud provider install "
            "`anthropic` or `openai` (conda-forge) and set ANTHROPIC_API_KEY / "
            "OPENAI_API_KEY. For a free local model install `openai` and point it "
            "at a server: --provider local with CHRONO_RAG_LLM_BASE_URL "
            "(e.g. Lemonade at http://localhost:13305/v1). `search` needs no key.",
            file=sys.stderr,
        )
        return 1
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    print(res["answer"])
    if res.get("sources"):
        print("\n[sources] " + ", ".join(res["sources"]))
    if res.get("model"):
        n = len(res["sources"])
        print(f"[answered by {res.get('provider')}/{res['model']}, "
              f"grounded in {n} source{'s' if n != 1 else ''}]")
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

    pa = sub.add_parser("ask", help="retrieve + LLM answer (cloud key or local server)")
    pa.add_argument("query", nargs="+", help="natural-language question")
    pa.add_argument("-k", type=int, default=8, help="chunks of context (default 8)")
    pa.add_argument("--model", default=None, help="LLM model id (default: provider default)")
    pa.add_argument(
        "--provider",
        choices=["anthropic", "openai", "local"],
        default=None,
        help="LLM backend (default: from CHRONO_RAG_LLM_* env, else auto)",
    )

    args = p.parse_args(argv)
    query = " ".join(args.query)
    if args.cmd == "search":
        return _cmd_search(query, args.k, args.full)
    if args.cmd == "ask":
        return _cmd_ask(query, args.k, args.model, args.provider)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
