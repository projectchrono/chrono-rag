r"""Append ProjectChrono Google Groups forum posts to a supplemental index.

Parses an mbox dump, produces one chunk per forum message (splitting long
ones), and appends to an existing index directory. If the directory has no
index yet it creates a fresh one. Idempotent: existing forum/* rows are
dropped and re-added on each run.

Memory-efficient: streams the mbox line-by-line, embeds and writes in
batches so the full 600 MB file is never loaded into RAM.

Run after build_examples_index.py so both sources share one index-new/ dir.

Usage:
  python src/preprocess/build_forum_index.py [mbox_path] [out_dir]

Defaults:
  mbox_path   <repo>/topics.mbox
  out_dir     <repo>/index-new

Env:
  CHRONO_RAG_EMBED_MODEL   embedding model (default: BAAI/bge-small-en-v1.5)
"""
from __future__ import annotations

import email
import email.header
import html
import json
import os
import re
import sys
import time
from typing import Generator

import numpy as np

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from core.embedder import DEFAULT_MODEL, get_embedder

MAX_CHARS = 1600
MIN_CHARS = 80
OVERLAP_LINES = 3
EMBED_BATCH = 512   # chunks per embedding call
MSG_TEXT_LIMIT = 8000  # max chars extracted per message before truncation


def _decode_header(value: str) -> str:
    parts = email.header.decode_header(value or "")
    out = []
    for raw, charset in parts:
        if isinstance(raw, bytes):
            out.append(raw.decode(charset or "utf-8", errors="ignore"))
        else:
            out.append(raw)
    return "".join(out).strip()


def _get_plain_text(msg: email.message.Message) -> str:
    plain = None
    for part in msg.walk():
        ct = part.get_content_type()
        if ct == "text/plain" and plain is None:
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                plain = payload.decode(charset, errors="ignore")
                if len(plain) > MSG_TEXT_LIMIT:
                    plain = plain[:MSG_TEXT_LIMIT]
    if plain is not None:
        return plain
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="ignore")[:MSG_TEXT_LIMIT * 3]
                text = re.sub(r"<[^>]+>", " ", text)
                return html.unescape(text)[:MSG_TEXT_LIMIT]
    return ""


def _strip_quoted(text: str) -> str:
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(">")]
    out, blanks = [], 0
    for ln in lines:
        if ln.strip() == "":
            blanks += 1
            if blanks <= 2:
                out.append(ln)
        else:
            blanks = 0
            out.append(ln)
    return "\n".join(out).strip()


def _make_chunk(path: str, line: int, text: str, symbol: str) -> dict:
    return {
        "path": path,
        "line": line,
        "text": text,
        "symbol": symbol,
        "language": "forum",
        "chunk_type": "post",
        "source": "projectchrono-forum",
    }


def _split_chunks(path: str, line: int, text: str, symbol: str) -> list[dict]:
    if len(text) <= MAX_CHARS:
        return [_make_chunk(path, line, text, symbol)]
    rows = text.split("\n")
    out: list[dict] = []
    i = 0
    while i < len(rows):
        cur, clen, j = [], 0, i
        while j < len(rows) and clen < MAX_CHARS:
            cur.append(rows[j])
            clen += len(rows[j]) + 1
            j += 1
        piece = "\n".join(cur).strip()
        if piece:
            out.append(_make_chunk(path, line + i, piece, symbol))
        if j >= len(rows):
            break
        i = max(j - OVERLAP_LINES, i + 1)
    return out


def _stream_messages(mbox_path: str) -> Generator[email.message.Message, None, None]:
    """Stream messages from mbox one at a time without loading the whole file."""
    buf: list[str] = []
    with open(mbox_path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if line.startswith("From ") and buf:
                try:
                    yield email.message_from_string("".join(buf))
                except Exception:
                    pass
                buf = [line]
            else:
                buf.append(line)
    if buf:
        try:
            yield email.message_from_string("".join(buf))
        except Exception:
            pass


def main() -> None:
    repo_root = os.path.normpath(os.path.join(_SRC, os.pardir))
    mbox_path = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(repo_root, "topics.mbox"))
    out_dir = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else os.path.join(repo_root, "index-new"))
    model_name = os.environ.get("CHRONO_RAG_EMBED_MODEL", DEFAULT_MODEL)

    print(f"[forum] mbox={mbox_path}")
    print(f"[forum] out={out_dir}")
    print(f"[forum] model={model_name}")
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()

    emb_path = os.path.join(out_dir, "embeddings.npy")
    meta_path = os.path.join(out_dir, "meta.jsonl")
    man_path = os.path.join(out_dir, "manifest.json")

    embedder = get_embedder(model_name)

    # Load existing non-forum chunks (idempotent: drop old forum/* rows)
    if os.path.exists(emb_path) and os.path.exists(meta_path):
        base_emb = np.load(emb_path).astype(np.float32)
        base_meta: list[dict] = []
        with open(meta_path, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    base_meta.append(json.loads(ln))
        keep = [i for i, m in enumerate(base_meta) if not str(m.get("path", "")).startswith("forum/")]
        base_emb = base_emb[keep]
        base_meta = [base_meta[i] for i in keep]
        print(f"[forum] retained {len(base_meta)} non-forum chunks from existing index")
    else:
        base_emb = np.zeros((0, embedder.dim), np.float32)
        base_meta = []

    manifest: dict = json.load(open(man_path, encoding="utf-8")) if os.path.exists(man_path) else {}

    # Stream mbox, embed in batches, write incrementally
    # Start output files fresh (forum section)
    all_emb_parts = [base_emb] if base_emb.shape[0] else []
    meta_fh = open(meta_path, "w", encoding="utf-8")
    for m in base_meta:
        meta_fh.write(json.dumps(m, ensure_ascii=False) + "\n")

    chunk_buf: list[dict] = []
    forum_chunks_total = 0
    thread_msg_count: dict[str, int] = {}
    skipped = 0
    msg_count = 0

    def flush_batch(buf: list[dict]) -> None:
        nonlocal forum_chunks_total
        if not buf:
            return
        texts = [c["text"] for c in buf]
        vecs = embedder.embed_documents(texts)
        all_emb_parts.append(vecs)
        for c in buf:
            meta_fh.write(json.dumps(c, ensure_ascii=False) + "\n")
        forum_chunks_total += len(buf)

    for msg in _stream_messages(mbox_path):
        msg_count += 1
        thread_id = msg.get("X-GM-THRID", "unknown")
        subject = _decode_header(msg.get("Subject", "(no subject)"))
        sender = _decode_header(msg.get("From", ""))
        date = msg.get("Date", "")

        body = _get_plain_text(msg)
        body = _strip_quoted(body)

        if len(body.strip()) < MIN_CHARS:
            skipped += 1
            continue

        sender_name = re.sub(r"<[^>]+>", "", sender).strip().strip('"')
        header = f"Subject: {subject}\nFrom: {sender_name}\nDate: {date}\n\n"
        full_text = header + body.strip()

        msg_idx = thread_msg_count.get(thread_id, 0) + 1
        thread_msg_count[thread_id] = msg_idx
        path = f"forum/{thread_id}"

        chunk_buf.extend(_split_chunks(path, msg_idx, full_text, subject))

        if len(chunk_buf) >= EMBED_BATCH:
            flush_batch(chunk_buf)
            chunk_buf = []
            elapsed = time.time() - t0
            print(f"[forum]   {msg_count} msgs processed, {forum_chunks_total} chunks embedded ({elapsed:.0f}s)")

    flush_batch(chunk_buf)  # remaining
    meta_fh.close()

    print(f"[forum] {forum_chunks_total} chunks from {len(thread_msg_count)} threads "
          f"({skipped}/{msg_count} messages skipped as too short)")

    # Concatenate and save final embeddings
    print("[forum] writing final embeddings.npy ...")
    emb = np.vstack(all_emb_parts).astype(np.float32) if all_emb_parts else np.zeros((0, embedder.dim), np.float32)
    np.save(emb_path, emb)

    manifest.update({
        "model": model_name,
        "dim": int(emb.shape[1]),
        "n_chunks": int(emb.shape[0]),
        "forum_chunks": forum_chunks_total,
        "forum_threads": len(thread_msg_count),
        "index_format": 2,
        "built_by": "chrono-rag build_forum_index",
    })
    with open(man_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"[forum] DONE: index now {emb.shape[0]} chunks in {time.time() - t0:.0f}s → {out_dir}")


if __name__ == "__main__":
    main()
