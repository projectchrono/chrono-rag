r"""Build the main Chrono RAG index.

Walks a Chrono checkout, chunks it structurally (AST for Python, tree-sitter for
C++), embeds with the local ONNX embedder, and writes the index artifact
(embeddings.npy + meta.jsonl + manifest.json).

Run (from the repo root):
  CHRONO_RAG_REPO=/path/to/chrono python -m chrono_rag.preprocess.build_index
Env:
  CHRONO_RAG_REPO         path to the Chrono checkout (required)
  CHRONO_RAG_INDEX        output index dir (default: <repo_root>/index)
  CHRONO_RAG_EMBED_MODEL  embedder (default: BAAI/bge-small-en-v1.5)
  CHRONO_RAG_VERSION      Chrono version number (default: parsed from CMakeLists)
  CHRONO_RAG_REF          git ref that was checked out (default: detected via git;
                          a release tag like "10.0.0", or a branch like "main")

The ref decides the user-facing scope label and the release "channel": a tag
yields "PyChrono 10.0" / channel "10.0.0"; a branch yields a dated
"Chrono main snapshot ..." label / channel "main", because Chrono's CMake
version stays at the last release between releases and would otherwise make a
development snapshot look like the release users have installed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

import numpy as np

from chrono_rag.core import config
from chrono_rag.core.embedder import DEFAULT_MODEL, get_embedder
from chrono_rag.preprocess.chunkers import chunk_file

CHUNKER_VERSION = "v2-structural-1"
MAX_FILE_BYTES = 1_000_000

_EXTS = {".h", ".hpp", ".hxx", ".cpp", ".cc", ".cxx", ".c", ".cu", ".cuh",
         ".py", ".cs", ".md", ".rst", ".txt"}
_EXTRA_NAMES = {"CMakeLists.txt", "README", "AGENTS.md", "CHANGELOG.md", "PLATFORMS.md"}
_SKIP_DIRS = {".git", "chrono_thirdparty", "data", "images"}
_SKIP_SUBSTR = ("_generated.h", ".yy.cpp", ".tab.c")


def _repo_or_die() -> str:
    """Resolve the Chrono checkout to index, or exit with clear guidance."""
    repo = os.environ.get("CHRONO_RAG_REPO") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not repo:
        print("error: no Chrono checkout given. Set CHRONO_RAG_REPO to your clone of "
              "https://github.com/projectchrono/chrono (or pass it as the first argument).",
              file=sys.stderr)
        raise SystemExit(2)
    repo = os.path.abspath(repo)
    if not os.path.isdir(repo):
        print(f"error: CHRONO_RAG_REPO points at {repo!r}, which is not a directory.",
              file=sys.stderr)
        raise SystemExit(2)
    return repo


def _repo_commit(repo: str) -> str:
    try:
        out = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _git(repo: str, *args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return ""


def _chrono_ref(repo: str) -> str:
    """The git ref that is checked out: CHRONO_RAG_REF, else an exact tag, else
    the branch name, else the short commit."""
    env = os.environ.get("CHRONO_RAG_REF")
    if env:
        return env.strip()
    tag = _git(repo, "describe", "--tags", "--exact-match")
    if tag:
        return tag
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch and branch != "HEAD":
        return branch
    return _git(repo, "rev-parse", "--short", "HEAD") or "unknown"


_TAG_RE = re.compile(r"^v?\d+\.\d+(\.\d+)?$")


def _is_release_ref(ref: str) -> bool:
    return bool(_TAG_RE.match(ref))


def _channel(ref: str) -> str:
    """Release channel name used in asset names and `get-index --channel`."""
    return ref.lstrip("v") if _is_release_ref(ref) else re.sub(r"[^A-Za-z0-9._-]+", "-", ref)


def _chrono_version(repo: str) -> str:
    env = os.environ.get("CHRONO_RAG_VERSION")
    if env:
        return env
    cml = os.path.join(repo, "CMakeLists.txt")
    try:
        with open(cml, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
        m = re.search(r"project\s*\(\s*Chrono[^\)]*VERSION\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text, re.I)
        if m:
            return m.group(1)
    except OSError:
        pass
    return "10.0"


def _version_label(version: str, ref: str, built_at: str) -> str:
    """The user-facing scope label printed with every answer.

    Release tag: '10.0.1' -> 'PyChrono 10.0'. Anything else is a development
    snapshot and says so, with the date, so a user on the conda release is not
    told about APIs that only exist on main (and vice versa).
    """
    major_minor = ".".join(version.split(".")[:2])
    if _is_release_ref(ref):
        return f"PyChrono {major_minor}"
    return f"Chrono {ref} snapshot {built_at} (post-{major_minor} development)"


def _want(path: str) -> bool:
    base = os.path.basename(path)
    if any(s in base for s in _SKIP_SUBSTR):
        return False
    if os.path.splitext(base)[1].lower() in _EXTS or base in _EXTRA_NAMES:
        try:
            return os.path.getsize(path) <= MAX_FILE_BYTES
        except OSError:
            return False
    return False


def _tracked_files(repo: str):
    """Paths git tracks in `repo` (None when it is not a git checkout).

    Indexing only tracked files keeps a developer's local build trees, scratch
    notes and generated wrappers (build_*/, *_proof/, ...) out of the index;
    a CI clone has none of those, so this makes local and CI builds agree.
    """
    out = _git(repo, "ls-files", "-z")
    if not out:
        return None
    return [os.path.join(repo, p) for p in out.split("\0") if p]


def _iter_files(repo: str):
    tracked = _tracked_files(repo)
    if tracked is not None:
        for full in tracked:
            rel = os.path.relpath(full, repo).replace("\\", "/")
            if any(part in _SKIP_DIRS for part in rel.split("/")[:-1]):
                continue
            if _want(full):
                yield full
        return
    for dirpath, dirnames, filenames in os.walk(repo):
        rel = os.path.relpath(dirpath, repo).replace("\\", "/")
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        if any(part in _SKIP_DIRS for part in rel.split("/")):
            continue
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            if _want(full):
                yield full


def main() -> None:
    repo = _repo_or_die()
    out = os.environ.get("CHRONO_RAG_INDEX") or config.index_dir()
    model_name = os.environ.get("CHRONO_RAG_EMBED_MODEL", DEFAULT_MODEL)
    os.makedirs(out, exist_ok=True)

    print(f"[build] repo={repo}")
    print(f"[build] out={out}")
    print(f"[build] model={model_name}")
    t0 = time.time()

    files = list(_iter_files(repo))
    print(f"[build] {len(files)} files to chunk")
    if not files:
        print(f"error: found no source files under {repo!r}. Is CHRONO_RAG_REPO "
              "pointing at a Chrono checkout?", file=sys.stderr)
        raise SystemExit(2)

    meta = []
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except OSError:
            continue
        rel = os.path.relpath(fpath, repo).replace("\\", "/")
        meta.extend(chunk_file(content, rel))

    print(f"[build] {len(meta)} chunks; embedding with {model_name} ...")
    embedder = get_embedder(model_name)
    texts = [m["text"] for m in meta]

    batch = 256
    vecs = []
    for i in range(0, len(texts), batch):
        vecs.append(embedder.embed_documents(texts[i:i + batch]))
        if (i // batch) % 20 == 0:
            print(f"[build]   embedded {min(i + batch, len(texts))}/{len(texts)}")
    emb = np.vstack(vecs).astype(np.float32)

    np.save(os.path.join(out, "embeddings.npy"), emb)
    with open(os.path.join(out, "meta.jsonl"), "w", encoding="utf-8") as fh:
        for m in meta:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")

    version = _chrono_version(repo)
    ref = _chrono_ref(repo)
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    manifest = {
        "model": model_name,
        "dim": int(emb.shape[1]),
        "n_chunks": int(emb.shape[0]),
        "n_files": len(files),
        "chunker_version": CHUNKER_VERSION,
        "index_format": 2,
        "commit": _repo_commit(repo),
        "chrono_version": version,
        "chrono_ref": ref,
        "channel": _channel(ref),
        "built_at": built_at,
        "version_label": _version_label(version, ref, built_at),
        "built_by": "chrono-rag",
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"[build] DONE: {emb.shape[0]} chunks, dim {emb.shape[1]}, "
          f"{len(files)} files, {time.time() - t0:.0f}s")
    print(f"[build] manifest: {json.dumps(manifest)}")


if __name__ == "__main__":
    main()
