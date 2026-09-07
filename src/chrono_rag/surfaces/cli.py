r"""Chrono RAG - command-line surface.

Subcommands over the shared retrieval core:
  search     - print the top retrieved Chrono/PyChrono chunks (no LLM, no key).
  ask        - BYOK: retrieve, then have an LLM answer from the retrieved context.
  get-index  - download the prebuilt search index from the GitHub Releases page.
  doctor     - check the local setup (index, model cache, keys, extras).

Run (after `pip install -e .`):
  chrono-rag search "how do I attach a lidar in pychrono"
  chrono-rag ask    "create a rigid body box in pychrono"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile

from chrono_rag.core import config


# ---------------------------------------------------------------------------
# search / ask
# ---------------------------------------------------------------------------

_MISSING_INDEX_HINT = (
    "\nGet one with `chrono-rag get-index` (downloads the prebuilt index), or "
    "build your own (see README, 'Build your own index')."
)


def _cmd_search(query: str, k: int, full: bool) -> int:
    from chrono_rag.surfaces.format import render_results

    try:
        print(render_results(query, k=k, full=full))
    except FileNotFoundError as e:
        print(f"error: {e}{_MISSING_INDEX_HINT}", file=sys.stderr)
        return 1
    return 0


def _cmd_ask(query: str, k: int, model: str | None, provider: str | None) -> int:
    try:
        from chrono_rag.surfaces.answer import answer as run_answer
        res = run_answer(query, k=k, model=model, provider=provider)
    except FileNotFoundError as e:
        print(f"error: {e}{_MISSING_INDEX_HINT}", file=sys.stderr)
        return 1
    except ImportError:
        print(
            "The 'ask' command needs an LLM SDK: install the extra with "
            "`pip install -e .[llm]`. For a cloud provider set ANTHROPIC_API_KEY / "
            "OPENAI_API_KEY. For a free local model point at a server: "
            "--provider local with CHRONO_RAG_LLM_BASE_URL "
            "(e.g. Lemonade at http://localhost:13305/v1). `search` needs no key.",
            file=sys.stderr,
        )
        return 1
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # LLM transport/auth errors: concise, no traceback
        msg = str(e)
        print(f"error: the LLM call failed: {msg}", file=sys.stderr)
        low = msg.lower()
        if any(s in low for s in ("401", "auth", "api key", "api_key", "permission")):
            print(
                "hint: check your API key (ANTHROPIC_API_KEY / OPENAI_API_KEY / "
                "CHRONO_RAG_LLM_API_KEY) and the --provider you selected.",
                file=sys.stderr,
            )
        return 1

    print(res["answer"])
    if res.get("sources"):
        print("\n[sources] " + ", ".join(res["sources"]))
    if res.get("model"):
        n = len(res["sources"])
        print(f"[answered by {res.get('provider')}/{res['model']}, "
              f"grounded in {n} source{'s' if n != 1 else ''}]")
    return 0


# ---------------------------------------------------------------------------
# get-index
# ---------------------------------------------------------------------------

def _http_get(url: str):
    """GET with a UA header (the GitHub API rejects UA-less requests)."""
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "chrono-rag"})
    return urllib.request.urlopen(req, timeout=60)


# Release-asset naming is the one contract between the publishing workflow
# (.github/workflows/index-release.yml) and this downloader:
#   chrono-rag-index-<channel>-<suffix>.zip (+ .sha256)
# where <channel> is "main" (dated development snapshot), a Chrono release tag
# such as "10.0.0", or "forum" (the optional forum+examples index). Newest
# release wins within a channel.
DEFAULT_CHANNEL = "main"


def _find_release_asset(channel: str) -> tuple[str, str | None]:
    """Return (zip_url, sha256_url_or_None) for the newest asset of `channel`."""
    url = f"https://api.github.com/repos/{config.GITHUB_REPO}/releases?per_page=50"
    with _http_get(url) as resp:
        releases = json.load(resp)
    prefix = f"chrono-rag-index-{channel}-"
    for rel in releases:  # newest first
        zip_url, sha_url = None, None
        for a in rel.get("assets", []):
            name = a.get("name", "")
            if not name.startswith(prefix):
                continue
            if name.endswith(".zip"):
                zip_url = a["browser_download_url"]
            elif name.endswith(".sha256"):
                sha_url = a["browser_download_url"]
        if zip_url:
            return zip_url, sha_url
    raise FileNotFoundError(
        f"no '{channel}' index asset found on https://github.com/{config.GITHUB_REPO}/releases "
        f"(channels: main, a Chrono release tag such as 10.0.0, or forum)"
    )


def _download(url: str, dest_path: str) -> None:
    print(f"[get-index] downloading {url.rsplit('/', 1)[-1]} ...")
    with _http_get(url) as resp, open(dest_path, "wb") as out:
        done = 0
        while True:
            block = resp.read(1 << 20)
            if not block:
                break
            out.write(block)
            done += len(block)
            if done % (10 << 20) < (1 << 20):
                print(f"[get-index]   {done / 1e6:.0f} MB ...")
    print(f"[get-index] downloaded {os.path.getsize(dest_path) / 1e6:.1f} MB")


def _verify_sha256(zip_path: str, sha_url: str | None) -> None:
    if not sha_url:
        print("[get-index] no .sha256 asset published; skipping checksum verification")
        return
    with _http_get(sha_url) as resp:
        expected = resp.read().decode("utf-8").split()[0].strip().lower()
    h = hashlib.sha256()
    with open(zip_path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    if h.hexdigest().lower() != expected:
        raise RuntimeError("sha256 mismatch: the downloaded index is corrupt; try again")
    print("[get-index] sha256 verified")


def _extract_index(zip_path: str, dest: str) -> None:
    """Extract the index zip so `dest` ends up holding embeddings.npy etc.

    Handles both layouts: files at the zip root, or under one top-level folder
    (the published assets use `index/...` / `index-forum/...`).
    """
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        tops = {n.split("/", 1)[0] for n in names if "/" in n}
        strip = tops.pop() + "/" if len(tops) == 1 and all("/" in n for n in names) else ""
        os.makedirs(dest, exist_ok=True)
        for n in names:
            target = os.path.join(dest, n[len(strip):]) if strip else os.path.join(dest, n)
            os.makedirs(os.path.dirname(target) or dest, exist_ok=True)
            with z.open(n) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def _cmd_get_index(forum: bool, force: bool, channel: str = DEFAULT_CHANNEL) -> int:
    if forum:
        channel = "forum"
        dest = os.path.join(os.path.dirname(config.index_dir()), "index-forum")
    else:
        dest = config.index_dir()
    if os.path.exists(os.path.join(dest, "embeddings.npy")) and not force:
        print(f"an index already exists at {dest}; re-run with --force to replace it.",
              file=sys.stderr)
        return 1

    try:
        zip_url, sha_url = _find_release_asset(channel)
        with tempfile.TemporaryDirectory() as tmp:
            zp = os.path.join(tmp, "index.zip")
            _download(zip_url, zp)
            _verify_sha256(zp, sha_url)
            _extract_index(zp, dest)
    except Exception as e:
        print(f"error: get-index failed: {e}", file=sys.stderr)
        print(f"You can also download it manually from "
              f"https://github.com/{config.GITHUB_REPO}/releases", file=sys.stderr)
        return 1

    print(f"[get-index] index ready at {dest}")
    man_path = os.path.join(dest, "manifest.json")
    if os.path.exists(man_path):
        with open(man_path, encoding="utf-8") as fh:
            man = json.load(fh)
        print(f"[get-index] scope: {man.get('version_label', '?')}  "
              f"(commit {str(man.get('commit', '?'))[:9]}, built {man.get('built_at', '?')})")
    if forum:
        sep = os.pathsep
        print(f"[get-index] enable it with:  CHRONO_RAG_EXTRA_INDEX={dest}")
        print(f"[get-index] (join multiple paths with '{sep}')")
    return 0


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

def _have(module: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module) is not None


def _model_cached(model_name: str) -> bool:
    """Heuristic: look for the embedding model in the usual local caches."""
    slug = model_name.split("/")[-1].lower()
    candidates = []
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        candidates.append(os.path.join(hf_home, "hub"))
    home = os.path.expanduser("~")
    candidates += [
        os.path.join(home, ".cache", "huggingface", "hub"),
        os.path.join(home, ".cache", "fastembed"),
        os.path.join(tempfile.gettempdir(), "fastembed_cache"),
    ]
    for root in candidates:
        if not os.path.isdir(root):
            continue
        for name in os.listdir(root):
            if slug in name.lower():
                return True
    return False


def _cmd_doctor() -> int:
    from chrono_rag import __version__

    ok = True
    print(f"chrono-rag {__version__}  (python {sys.version.split()[0]})")

    # 1. index
    idx = config.index_dir()
    man_path = os.path.join(idx, "manifest.json")
    if os.path.exists(os.path.join(idx, "embeddings.npy")):
        man = {}
        if os.path.exists(man_path):
            with open(man_path, encoding="utf-8") as fh:
                man = json.load(fh)
        print(f"[ok]   index: {idx}")
        print(f"       {man.get('n_chunks', '?')} chunks, model {man.get('model', '?')}, "
              f"chrono {man.get('chrono_version', '?')}")
        print(f"       scope: {man.get('version_label', '?')}; channel "
              f"{man.get('channel', '?')}, ref {man.get('chrono_ref', '?')}, "
              f"commit {str(man.get('commit', '?'))[:9]}, built {man.get('built_at', '?')}")
    else:
        print(f"[MISS] index: nothing at {idx}")
        print("       fix: run `chrono-rag get-index` (or set CHRONO_RAG_INDEX)")
        ok = False

    # 2. extra indexes
    for d in config.extra_index_dirs():
        state = "ok" if os.path.exists(os.path.join(d, "embeddings.npy")) else "MISS"
        print(f"[{state:4}] extra index: {d}")
        if state == "MISS":
            ok = False

    # 3. embedding model cache (heuristic)
    from chrono_rag.core.embedder import DEFAULT_MODEL

    if _model_cached(DEFAULT_MODEL):
        print(f"[ok]   embedding model cached: {DEFAULT_MODEL}")
    else:
        print(f"[note] embedding model not cached yet: {DEFAULT_MODEL}")
        print("       the first search downloads it once (~130 MB); network needed")

    # 4. optional surfaces / extras
    print(f"[{'ok' if _have('mcp') else 'note':4}] MCP surface "
          f"({'installed' if _have('mcp') else 'pip install -e .[mcp]'})")
    print(f"[{'ok' if _have('fastapi') else 'note':4}] web surface "
          f"({'installed' if _have('fastapi') else 'pip install -e .[web]'})")

    # 5. answer LLM
    have_llm_sdk = _have("anthropic") or _have("openai")
    if not have_llm_sdk:
        print("[note] no LLM SDK installed; `search` works, `ask` needs "
              "`pip install -e .[llm]`")
    else:
        keys = [v for v in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CHRONO_RAG_LLM_API_KEY")
                if os.getenv(v)]
        base = config.llm_base_url()
        try:
            from chrono_rag.inference.llm import LLM

            llm = LLM()
            print(f"[ok]   ask would use: {llm.provider}/{llm.model}"
                  + (f" via {base}" if base else ""))
            if llm.provider != "local" and not keys:
                print("[note] no API key set; set ANTHROPIC_API_KEY or OPENAI_API_KEY "
                      "(or use a local server)")
        except ValueError as e:
            print(f"[note] ask not configured: {e}")

    print("\nresult:", "ready" if ok else "needs attention (see [MISS] above)")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="chrono-rag",
        description="Local Chrono/PyChrono retrieval assistant over an index of Chrono's "
                    "own code and docs (the loaded index's scope is printed with every result).",
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

    pg = sub.add_parser("get-index", help="download a prebuilt index from GitHub Releases")
    pg.add_argument("--channel", default=DEFAULT_CHANNEL,
                    help="which index: 'main' (dated snapshot of Chrono's development branch, "
                         "default) or a Chrono release tag such as '10.0.0' (what conda "
                         "PyChrono users have)")
    pg.add_argument("--forum", action="store_true",
                    help="download the optional forum+examples index instead")
    pg.add_argument("--force", action="store_true", help="replace an existing index")

    sub.add_parser("doctor", help="check the local setup (index, model cache, keys)")

    args = p.parse_args(argv)
    if args.cmd == "search":
        return _cmd_search(" ".join(args.query), args.k, args.full)
    if args.cmd == "ask":
        return _cmd_ask(" ".join(args.query), args.k, args.model, args.provider)
    if args.cmd == "get-index":
        return _cmd_get_index(args.forum, args.force, args.channel)
    if args.cmd == "doctor":
        return _cmd_doctor()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
