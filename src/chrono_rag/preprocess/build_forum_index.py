r"""Append ProjectChrono Google Groups forum posts to a supplemental index.

Parses an mbox dump, produces one chunk per forum message (splitting long
ones), and appends to an existing index directory. If the directory has no
index yet it creates a fresh one. Idempotent: existing forum/* rows are
dropped and re-added on each run.

Curation: drops messages older than MIN_YEAR (stale advice, esp. install
instructions for versions long gone) and drops install/build/compile
threads (they go stale fastest and the docs cover current install).

Privacy: the chunk header carries only Subject/Date, never the sender's name
or email. Email addresses, quoted reply-header blocks (Outlook-style
"From:/Sent:/To:/Subject:" top-posting), the Google Groups unsubscribe
footer, and the sender's own name are stripped from the body text.

Memory-efficient: streams the mbox line-by-line, embeds and writes in
batches so the full 600 MB file is never loaded into RAM.

Run after build_examples_index.py so both sources share one index-forum/ dir.

Usage (from the repo root):
  python -m chrono_rag.preprocess.build_forum_index [mbox_path] [out_dir]

Defaults (relative to the current directory):
  mbox_path   ./topics.mbox
  out_dir     ./index-forum

Env:
  CHRONO_RAG_EMBED_MODEL   embedding model (default: BAAI/bge-small-en-v1.5)
"""
from __future__ import annotations

import email
import email.header
import email.utils
import html
import json
import os
import re
import sys
import time
from typing import Generator, Optional

import numpy as np

from chrono_rag.core.embedder import DEFAULT_MODEL, get_embedder

MAX_CHARS = 1600
MIN_CHARS = 80
OVERLAP_LINES = 3
EMBED_BATCH = 512   # chunks per embedding call
MSG_TEXT_LIMIT = 8000  # max chars extracted per message before truncation
MIN_YEAR = 2020  # drop older posts: stale advice, esp. install instructions

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_UNSUBSCRIBE_RE = re.compile(
    r"You received this message because you are subscribed.*?googlegroups\.com\.?"
    r"(<mailto:[^>]*>)?",
    re.I | re.S,
)
# Gmail/Apple-style quote attribution ("On <date>, <Name> <email> wrote:"). The
# email inside is sometimes line-wrapped, so the body of the match spans newlines.
_QUOTE_ATTRIBUTION_RE = re.compile(r"^[ \t>]*On [\s\S]{1,180}?wrote:[ \t]*$", re.I | re.M)
# Outlook-style top-posted reply headers embedded in the body (not quoted with ">").
# Field order/set varies a lot across mail clients, so just require a From: line
# followed within a handful of lines by a Subject: line -- that pairing is specific
# enough to real reply-header blocks that it won't fire on ordinary body text.
_REPLY_HEADER_RE = re.compile(r"^[ \t]*From:.*(?:\n.*){0,6}?\n[ \t]*Subject:.*\n?", re.I | re.M)
_INSTALL_RE = re.compile(
    r"\b(install(ation|ing|ed)?|compil(e|ing|ation)|cmake|linker error|link error|"
    r"undefined reference|build (error|fail|issue)s?|failing to build|"
    r"building chrono|build chrono|configuring chrono)\b",
    re.I,
)
# Greeting / vocative openers ("Hi Radu,", "Dear Tobias", "Thanks Marco,"). Only the
# sender's own name is known from the header, so a recipient/third-party first name in an
# opening greeting is the common residual. Strip the capitalized name token(s) right after
# a greeting word. Kept deliberately narrow (greeting word + Capitalized name at a line
# start, followed by punctuation or end of line) so it does not eat ordinary Capitalized
# words mid-sentence or API names like "Hi ChBody works".
_GREETING_RE = re.compile(
    r"(?m)^([ \t]*(?i:hi|hello|dear|hey|thanks|thank you|thankyou)\b[ \t]+)"
    r"[A-Z][A-Za-z'’.\-]+(?:[ \t]+[A-Z][A-Za-z'’.\-]+)?"
    r"(?=[ \t]*[,:!.]|[ \t]*$)"
)


def _normalize_subject(subject: str) -> str:
    s = subject
    for _ in range(3):
        stripped = re.sub(r"^\s*(re|fwd?)\s*:\s*", "", s, flags=re.I)
        stripped = re.sub(r"^\s*\[chrono\]\s*", "", stripped, flags=re.I)
        if stripped == s:
            break
        s = stripped
    return s.strip()


def _is_install_thread(subject: str) -> bool:
    return bool(_INSTALL_RE.search(_normalize_subject(subject)))


def _post_year(date_header: str) -> Optional[int]:
    try:
        return email.utils.parsedate_to_datetime(date_header).year
    except Exception:
        return None


def _truncate_at_quote_boundary(text: str) -> str:
    """Cut a message at its first nested-quote marker.

    Top-posted replies re-quote the entire prior thread below the new content,
    which is both redundant (same text re-indexed once per reply) and where
    third-party names/emails accumulate as the thread grows. Keeping only the
    text above the first quote boundary discards that baggage in one step
    instead of trying to selectively redact names buried inside it.
    """
    cut = len(text)
    for pat in (_REPLY_HEADER_RE, _QUOTE_ATTRIBUTION_RE):
        m = pat.search(text)
        if m:
            cut = min(cut, m.start())
    return text[:cut].rstrip()


def _scrub_pii(text: str, sender_name: str) -> str:
    text = _truncate_at_quote_boundary(text)
    text = _UNSUBSCRIBE_RE.sub("", text)
    text = _EMAIL_RE.sub("[email removed]", text)
    if sender_name:
        for part in sender_name.split():
            part = re.escape(part.strip("'\""))
            if len(part) > 2:
                text = re.sub(rf"\b{part}\b", "[name removed]", text)
    text = _GREETING_RE.sub(lambda m: m.group(1) + "[name removed]", text)
    return text


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
                # Drop <style>/<script> bodies first; stripping only tags would leave
                # their CSS/JS text (e.g. @font-face rules) in the indexed chunk.
                text = re.sub(r"(?is)<(style|script)\b[^>]*>.*?</\1>", " ", text)
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
    mbox_path = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "topics.mbox")
    out_dir = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else "index-forum")
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
    skipped_old = 0
    skipped_install = 0
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

        year = _post_year(date)
        if year is not None and year < MIN_YEAR:
            skipped_old += 1
            continue

        if _is_install_thread(subject):
            skipped_install += 1
            continue

        body = _get_plain_text(msg)
        body = _strip_quoted(body)

        if len(body.strip()) < MIN_CHARS:
            skipped += 1
            continue

        sender_name = re.sub(r"<[^>]+>", "", sender).strip().strip('"')
        body = _scrub_pii(body, sender_name)
        clean_subject = _EMAIL_RE.sub("[email removed]", subject)
        header = f"Subject: {clean_subject}\nDate: {date}\n\n"
        full_text = header + body.strip()

        msg_idx = thread_msg_count.get(thread_id, 0) + 1
        thread_msg_count[thread_id] = msg_idx
        path = f"forum/{thread_id}"

        chunk_buf.extend(_split_chunks(path, msg_idx, full_text, clean_subject))

        if len(chunk_buf) >= EMBED_BATCH:
            flush_batch(chunk_buf)
            chunk_buf = []
            elapsed = time.time() - t0
            print(f"[forum]   {msg_count} msgs processed, {forum_chunks_total} chunks embedded ({elapsed:.0f}s)")

    flush_batch(chunk_buf)  # remaining
    meta_fh.close()

    print(f"[forum] {forum_chunks_total} chunks from {len(thread_msg_count)} threads "
          f"({skipped}/{msg_count} too short, {skipped_old} pre-{MIN_YEAR}, "
          f"{skipped_install} install/build threads)")

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

    print(f"[forum] DONE: index now {emb.shape[0]} chunks in {time.time() - t0:.0f}s -> {out_dir}")


if __name__ == "__main__":
    main()
