"""Structural chunkers producing chunks with real line numbers + symbols.

- Python: AST-based. Emits top-level functions/classes AND the module-level
  script body (PyChrono demos are scripts, not libraries, so the body matters).
- C++: tree-sitter (prebuilt grammar wheel, no compiler). Emits classes/structs
  and function definitions with their leading Doxygen comment.
- Other (json/md/rst/txt/cmake): size-windowed fallback.

Every chunk is a dict: {path, line, text, symbol, language, chunk_type}.
"""
from __future__ import annotations

import ast
import os
import re
from typing import Dict, List, Optional

# Chrono export macros (ChApi, ChApiVehicle, CH_..._API, ...) appear between
# `class`/`struct` and the type name and break tree-sitter's parse. Blank them
# (preserving length so byte offsets and line numbers stay exact).
_MACRO_RE = re.compile(r"\bChApi\w*\b|\bCH_[A-Z0-9_]*API[A-Z0-9_]*\b")


def _strip_macros(text: str) -> str:
    return _MACRO_RE.sub(lambda m: " " * (m.end() - m.start()), text)

MAX_CHARS = 1600
OVERLAP_LINES = 5

EXT_LANG = {
    ".py": "py", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".c": "c",
    ".h": "cpp", ".hpp": "cpp", ".hxx": "cpp", ".cu": "cpp", ".cuh": "cpp",
    ".cs": "cs", ".md": "md", ".rst": "rst", ".txt": "txt",
}


def lang_for(path: str) -> str:
    base = os.path.basename(path)
    if base == "CMakeLists.txt" or base.endswith(".cmake"):
        return "cmake"
    return EXT_LANG.get(os.path.splitext(base)[1].lower(), "")


def _chunk(path, line, text, symbol, language, chunk_type) -> Dict:
    return {
        "path": path, "line": int(line), "text": text,
        "symbol": symbol, "language": language, "chunk_type": chunk_type,
    }


def _split_oversized(path, line, text, symbol, language, chunk_type) -> List[Dict]:
    """Split a chunk whose text exceeds MAX_CHARS into line-windowed sub-chunks
    that preserve accurate start lines."""
    if len(text) <= MAX_CHARS:
        return [_chunk(path, line, text, symbol, language, chunk_type)] if text.strip() else []
    lines = text.split("\n")
    out: List[Dict] = []
    i = 0
    while i < len(lines):
        cur, clen, j = [], 0, i
        while j < len(lines) and clen < MAX_CHARS:
            cur.append(lines[j])
            clen += len(lines[j]) + 1
            j += 1
        piece = "\n".join(cur)
        if piece.strip():
            out.append(_chunk(path, line + i, piece, symbol, language, chunk_type))
        if j >= len(lines):
            break
        i = max(j - OVERLAP_LINES, i + 1)
    return out


# --------------------------------------------------------------------------- #
# Python (AST)
# --------------------------------------------------------------------------- #

def chunk_python(content: str, path: str) -> List[Dict]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return _windowed(content, path, "py")

    lines = content.splitlines()

    import_lines: List[str] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.extend(lines[node.lineno - 1: node.end_lineno])
    header = "\n".join(import_lines)

    out: List[Dict] = []
    body_run: List[ast.stmt] = []

    def flush_body():
        if not body_run:
            return
        start = body_run[0].lineno
        end = body_run[-1].end_lineno or start
        text = "\n".join(lines[start - 1: end])
        out.extend(_split_oversized(path, start, text, os.path.basename(path), "py", "module"))
        body_run.clear()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            flush_body()
            seg = "\n".join(lines[node.lineno - 1: node.end_lineno])
            text = f"{header}\n\n{seg}" if header else seg
            ctype = "class" if isinstance(node, ast.ClassDef) else "function"
            out.extend(_split_oversized(path, node.lineno, text, node.name, "py", ctype))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            continue  # already captured in header
        else:
            body_run.append(node)
    flush_body()

    return out or _windowed(content, path, "py")


# --------------------------------------------------------------------------- #
# C++ (tree-sitter)
# --------------------------------------------------------------------------- #

_CPP_PARSER = None
_CONTAINER_TYPES = {
    "translation_unit", "namespace_definition", "linkage_specification",
    "declaration_list", "preproc_if", "preproc_ifdef", "preproc_else",
}
_TARGET_TYPES = {"class_specifier", "struct_specifier", "function_definition"}


def _cpp_parser():
    global _CPP_PARSER
    if _CPP_PARSER is None:
        from tree_sitter import Language, Parser
        import tree_sitter_cpp
        lang = Language(tree_sitter_cpp.language())
        try:
            _CPP_PARSER = Parser(lang)
        except TypeError:  # older API
            _CPP_PARSER = Parser()
            _CPP_PARSER.language = lang
    return _CPP_PARSER


def _node_text(src: bytes, node) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", "ignore")


def _find_descendant(node, type_name: str):
    """Breadth-first search for the first descendant of the given type."""
    queue = list(node.children)
    while queue:
        n = queue.pop(0)
        if n.type == type_name:
            return n
        queue.extend(n.children)
    return None


def _func_name(node) -> Optional[str]:
    """Name of a function_definition, including any class qualifier
    (e.g. 'ChBody::SetPos')."""
    decl = _find_descendant(node, "function_declarator")
    if decl is None:
        return None
    name = decl.child_by_field_name("declarator")
    if name is None:
        return None
    return name.text.decode("utf-8", "ignore").strip()


def chunk_cpp(content: str, path: str) -> List[Dict]:
    try:
        parser = _cpp_parser()
        src = bytes(_strip_macros(content), "utf-8")
        root = parser.parse(src).root_node
    except Exception:
        return _windowed(content, path, "cpp")

    out: List[Dict] = []

    def visit(node):
        for child in node.children:
            if child.type in _TARGET_TYPES:
                name = None
                ctype = "function"
                if child.type == "class_specifier":
                    ctype = "class"
                elif child.type == "struct_specifier":
                    ctype = "struct"
                if ctype in ("class", "struct"):
                    nm = child.child_by_field_name("name")
                    name = nm.text.decode("utf-8", "ignore") if nm else None
                else:
                    name = _func_name(child)
                # include immediately-preceding comment (Doxygen)
                start_node = child
                prev = child.prev_sibling
                if prev is not None and prev.type == "comment":
                    start_node = prev
                text = _node_text(src, start_node) if start_node is child else (
                    _node_text(src, prev) + "\n" + _node_text(src, child)
                )
                line = start_node.start_point[0] + 1
                out.extend(_split_oversized(path, line, text, name or "", "cpp", ctype))
            elif child.type in _CONTAINER_TYPES:
                visit(child)

    visit(root)
    return out or _windowed(content, path, "cpp")


# --------------------------------------------------------------------------- #
# Fallback + dispatcher
# --------------------------------------------------------------------------- #

def _windowed(content: str, path: str, language: str) -> List[Dict]:
    return _split_oversized(path, 1, content, os.path.basename(path), language, "file")


def chunk_file(content: str, path: str) -> List[Dict]:
    language = lang_for(path)
    if language == "py":
        return chunk_python(content, path)
    if language in ("cpp", "c"):
        return chunk_cpp(content, path)
    return _windowed(content, path, language or "txt")
