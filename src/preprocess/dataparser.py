"""
Clones Chrono repos and produces semantically-chunked Document objects.

Repos:
  Chrono:           https://github.com/projectchrono/chrono
  PyChrono Examples: https://github.com/projectchrono/pychrono-examples-9.0
"""
from __future__ import annotations

import ast
import mailbox
import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from email.header import decode_header as _decode_header
from email.utils import parsedate_to_datetime
from typing import Generator, List, Optional


@dataclass
class Document:
    content: str
    source_repo: str    # "chrono" | "pychrono-examples"
    file_path: str      # relative to repo root
    language: str       # "py" | "cpp" | "json"
    chunk_type: str     # "class" | "function" | "file"
    chunk_name: str
    embedding: List[float] = field(default_factory=list)
    answer: str = ""


def clone_repo(url: str, dest: str) -> None:
    if os.path.exists(dest):
        return
    subprocess.run(["git", "clone", "--depth", "1", url, dest], check=True)


_SUPPORTED_EXTENSIONS = {".py", ".cpp", ".h", ".hpp", ".json"}


def walk_path(base_dir: str, rel_path: str, recursive: bool) -> Generator[str, None, None]:
    target = os.path.join(base_dir, rel_path) if rel_path else base_dir
    if not os.path.exists(target):
        return

    if recursive:
        for root, _, files in os.walk(target):
            for fname in files:
                if os.path.splitext(fname)[1] in _SUPPORTED_EXTENSIONS:
                    yield os.path.join(root, fname)
    else:
        for fname in os.listdir(target):
            fpath = os.path.join(target, fname)
            if os.path.isfile(fpath) and os.path.splitext(fname)[1] in _SUPPORTED_EXTENSIONS:
                yield fpath


def chunk_python_file(content: str, file_path: str, source_repo: str) -> List[Document]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return [Document(
            content=content, source_repo=source_repo, file_path=file_path,
            language="py", chunk_type="file", chunk_name=os.path.basename(file_path),
        )]

    lines = content.splitlines()

    import_lines: List[str] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.extend(lines[node.lineno - 1 : node.end_lineno])
    import_header = "\n".join(import_lines)

    chunks: List[Document] = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body_text = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            chunk_content = f"{import_header}\n\n{body_text}" if import_header else body_text
            chunks.append(Document(
                content=chunk_content,
                source_repo=source_repo,
                file_path=file_path,
                language="py",
                chunk_type="class" if isinstance(node, ast.ClassDef) else "function",
                chunk_name=node.name,
            ))

    return chunks or [Document(
        content=content, source_repo=source_repo, file_path=file_path,
        language="py", chunk_type="file", chunk_name=os.path.basename(file_path),
    )]


# Matches class/struct definitions at the start of a line (for headers)
_CLASS_RE = re.compile(r"^(class|struct)\s+(\w+)", re.MULTILINE)
# Matches method implementations: ReturnType ClassName::MethodName(
_METHOD_RE = re.compile(r"^(?!#)(?!//)[\w][\w\s*&<>:,]*\s+(\w+)::(\w+)\s*\(", re.MULTILINE)


def chunk_cpp_file(content: str, file_path: str, source_repo: str) -> List[Document]:
    is_header = file_path.endswith((".h", ".hpp"))
    pattern = _CLASS_RE if is_header else _METHOD_RE

    matches = list(pattern.finditer(content))
    if not matches:
        return [Document(
            content=content, source_repo=source_repo, file_path=file_path,
            language="cpp", chunk_type="file", chunk_name=os.path.basename(file_path),
        )]

    positions = [m.start() for m in matches] + [len(content)]
    chunk_type = "class" if is_header else "function"

    chunks: List[Document] = []
    for i, match in enumerate(matches):
        chunk_content = content[positions[i] : positions[i + 1]].strip()
        if is_header:
            chunk_name = match.group(2)
        else:
            chunk_name = f"{match.group(1)}::{match.group(2)}"

        chunks.append(Document(
            content=chunk_content,
            source_repo=source_repo,
            file_path=file_path,
            language="cpp",
            chunk_type=chunk_type,
            chunk_name=chunk_name,
        ))

    return chunks


def chunk_json_file(content: str, file_path: str, source_repo: str) -> List[Document]:
    return [Document(
        content=content,
        source_repo=source_repo,
        file_path=file_path,
        language="json",
        chunk_type="file",
        chunk_name=os.path.basename(file_path),
    )]


def parse_file(abs_path: str, rel_path: str, source_repo: str) -> List[Document]:
    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
    except OSError:
        return []

    if abs_path.endswith(".py"):
        return chunk_python_file(content, rel_path, source_repo)
    if abs_path.endswith((".cpp", ".h", ".hpp")):
        return chunk_cpp_file(content, rel_path, source_repo)
    if abs_path.endswith(".json"):
        return chunk_json_file(content, rel_path, source_repo)
    return []


_CHRONO_URL = "https://github.com/projectchrono/chrono"
_PYCHRONO_URL = "https://github.com/projectchrono/pychrono-examples-9.0"

# (path relative to repo root, recursive)
_CHRONO_PATHS = [
    ("src/chrono_vehicle/wheeled_vehicle/suspension", True),
    ("src/chrono_vehicle/wheeled_vehicle/vehicle", True),
    ("src/chrono_vehicle", False),  # top-level only
    ("data/vehicle/hmmwv", True),
    ("src/demos/python/chrono_vehicle", True),
]

_PYCHRONO_PATHS = [
    ("", True),  # full repo
]


def parse_repos(repos_dir: str) -> Generator[Document, None, None]:
    chrono_dir = os.path.join(repos_dir, "chrono")
    pychrono_dir = os.path.join(repos_dir, "pychrono-examples")

    clone_repo(_CHRONO_URL, chrono_dir)
    clone_repo(_PYCHRONO_URL, pychrono_dir)

    for rel_path, recursive in _CHRONO_PATHS:
        for abs_path in walk_path(chrono_dir, rel_path, recursive):
            rel = os.path.relpath(abs_path, chrono_dir)
            yield from parse_file(abs_path, rel, "chrono")

    for rel_path, recursive in _PYCHRONO_PATHS:
        for abs_path in walk_path(pychrono_dir, rel_path, recursive):
            rel = os.path.relpath(abs_path, pychrono_dir)
            yield from parse_file(abs_path, rel, "pychrono-examples")


def parse_example_pair(input_path: str, truth_path: str) -> Document:
    with open(input_path, "r", encoding="utf-8") as fh:
        prompt = fh.read()
    with open(truth_path, "r", encoding="utf-8") as fh:
        code = fh.read()
    return Document(
        content=prompt,
        answer=code,
        source_repo="example",
        file_path=input_path,
        language="text",
        chunk_type="example",
        chunk_name=os.path.basename(input_path),
    )


def parse_example_pairs(pairs: List[tuple]) -> List[Document]:
    return [parse_example_pair(inp, truth) for inp, truth in pairs]


# ---------------------------------------------------------------------------
# mbox / mailing-list parser
# ---------------------------------------------------------------------------

def _decode_str(value: Optional[str]) -> str:
    if not value:
        return ""
    parts = []
    for fragment, charset in _decode_header(value):
        if isinstance(fragment, bytes):
            parts.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(fragment)
    return "".join(parts)


def _extract_plain_body(msg) -> str:
    """Return decoded text/plain body, preferring the first such part."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        return ""
    if msg.get_content_type() == "text/plain":
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace") if payload else ""
    return ""


def _msg_date(msg) -> float:
    try:
        return parsedate_to_datetime(msg["Date"]).timestamp()
    except Exception:
        return 0.0


def _format_thread(messages: list) -> str:
    parts = []
    for msg in messages:
        sender = _decode_str(msg["From"])
        date = msg["Date"] or ""
        body = _extract_plain_body(msg).strip()
        parts.append(f"--- {sender} ({date}) ---\n{body}")
    return "\n\n".join(parts)


def parse_mbox(mbox_path: str) -> Generator[Document, None, None]:
    """Parse an mbox file and yield one Document per email thread."""
    mb = mailbox.mbox(mbox_path, create=False)

    # Group message objects by Gmail thread ID, falling back to Message-Id.
    threads: dict[str, list] = defaultdict(list)
    subjects: dict[str, str] = {}

    for msg in mb:
        thread_id = msg.get("X-GM-THRID") or msg.get("Message-Id") or "unknown"
        threads[thread_id].append(msg)
        if thread_id not in subjects:
            raw_subject = _decode_str(msg.get("Subject", ""))
            # Strip reply prefixes to get the canonical subject
            subjects[thread_id] = re.sub(r"^(Re|RE|Fwd|FW):\s*(\[.*?\]\s*)?", "", raw_subject).strip()

    for thread_id, messages in threads.items():
        messages.sort(key=_msg_date)
        subject = subjects.get(thread_id, "unknown")
        question = f"Subject: {subject}\n\n{_format_thread(messages[:1])}"
        answers = _format_thread(messages[1:]) if len(messages) > 1 else ""
        yield Document(
            content=question,
            answer=answers,
            source_repo="mailing-list",
            file_path=f"mbox://thread/{thread_id}",
            language="text",
            chunk_type="thread",
            chunk_name=subject,
        )
