"""Hybrid retrieval core: dense + BM25 + symbol, fused with reciprocal-rank.

Produces ranked results plus an abstention signal and per-chunk injection flags.
The abstention signal is *advisory*: the MCP surface returns it without
hard-blocking (it cannot enforce refusal anyway), while the answer surface
(CLI / web) uses it to hard-refuse below a calibrated bar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import config
from .bm25 import BM25Index
from .embedder import DEFAULT_MODEL, Embedder, get_embedder
from .store import VectorStore, load_store

# Prompt-injection / meta-instruction patterns that may appear inside corpus
# text (docs, comments, issue templates). Flagged chunks are down-ranked.
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"\byou\s+are\s+(an?\s+)?(ai|assistant|language model)\b", re.I),
    re.compile(r"\bsystem\s+prompt\b", re.I),
    re.compile(r"\bdisregard\s+(the\s+)?(above|previous)\b", re.I),
    re.compile(r"</?(system|instructions?)>", re.I),
]


def looks_like_injection(text: str) -> bool:
    return any(p.search(text) for p in _INJECTION_PATTERNS)


def _lang_of(meta: Dict[str, Any]) -> str:
    return meta.get("language", "")


def _is_python_chunk(meta: Dict[str, Any]) -> bool:
    if _lang_of(meta) == "py":
        return True
    path = meta.get("path", "").lower()
    return "/python/" in path or "pychrono" in path


def _is_forum_chunk(meta: Dict[str, Any]) -> bool:
    return _lang_of(meta) == "forum" or meta.get("source") == "projectchrono-forum"


def _is_pychrono_query(query: str) -> bool:
    q = query.lower()
    return (
        "pychrono" in q
        or "python" in q
        or "chrono." in q
        or bool(re.search(r"\bimport\s+chrono\b", q))
    )


@dataclass
class Result:
    rank: int
    score: float
    path: str
    line: int
    language: str
    chunk_type: str
    symbol: str
    text: str
    dense_score: float = 0.0
    bm25_score: float = 0.0
    flagged_injection: bool = False


@dataclass
class Retrieval:
    query: str
    results: List[Result]
    insufficient_evidence: bool
    confidence: float
    version_label: str = config.VERSION_LABEL
    notes: List[str] = field(default_factory=list)


class RetrievalCore:
    """Hybrid search over the in-memory index. Build once and reuse (it holds the
    warm embedder and the BM25/symbol indexes)."""

    def __init__(
        self,
        store: Optional[VectorStore] = None,
        embedder: Optional[Embedder] = None,
        build_bm25: bool = True,
    ) -> None:
        self.store = store or load_store()
        model = self.store.model_name or DEFAULT_MODEL
        self.embedder = embedder or get_embedder(model)
        # The user-facing scope label follows the index that is actually loaded
        # (written at build time); the config constant is only the fallback.
        self.version_label = self.store.manifest.get("version_label") or config.VERSION_LABEL
        self._bm25 = (
            BM25Index([m.get("text", "") for m in self.store.meta]) if build_bm25 else None
        )
        self._symbol_index = self._build_symbol_index()

    def _build_symbol_index(self) -> Dict[str, List[int]]:
        idx: Dict[str, List[int]] = {}
        for i, m in enumerate(self.store.meta):
            sym = m.get("symbol")
            if not sym:
                continue
            tail = re.split(r"::|\.", sym)[-1]
            for key in {sym.lower(), tail.lower()}:
                if key:
                    idx.setdefault(key, []).append(i)
        return idx

    def _symbol_hits(self, query: str, limit: int) -> List[int]:
        if not self._symbol_index:
            return []
        hits: List[int] = []
        seen = set()
        for tok in re.findall(r"[A-Za-z_][\w:]*", query):
            for piece in re.split(r"::|\.", tok):
                key = piece.lower()
                for i in self._symbol_index.get(key, [])[:5]:
                    if i not in seen:
                        seen.add(i)
                        hits.append(i)
        return hits[:limit]

    @staticmethod
    def _rrf(rank_lists: List[List[int]]) -> Dict[int, float]:
        scores: Dict[int, float] = {}
        for lst in rank_lists:
            for rank, idx in enumerate(lst):
                scores[idx] = scores.get(idx, 0.0) + 1.0 / (config.RRF_K + rank + 1)
        return scores

    def search(self, query: str, k: int = 8, candidate_k: int = 50) -> Retrieval:
        meta = self.store.meta

        dense = self.store.dense_search(self.embedder.embed_query(query), candidate_k)
        dense_ranked = [i for i, _ in dense]
        dense_score = {i: s for i, s in dense}

        bm = self._bm25.search(query, candidate_k) if self._bm25 else []
        bm_ranked = [i for i, _ in bm]
        bm_score = {i: s for i, s in bm}

        sym_ranked = self._symbol_hits(query, candidate_k)

        fused = self._rrf([dense_ranked, bm_ranked, sym_ranked])

        pyq = _is_pychrono_query(query)
        flagged = {i: looks_like_injection(meta[i].get("text", "")) for i in fused}
        for i in list(fused):
            if pyq and _is_python_chunk(meta[i]):
                fused[i] += config.PYCHRONO_BOOST
            if _is_forum_chunk(meta[i]):
                fused[i] -= config.FORUM_PENALTY
            if flagged[i]:
                fused[i] -= 1.0  # bury flagged chunks; still surfaced if nothing else

        order = sorted(fused, key=lambda i: -fused[i])[:k]
        results = [
            Result(
                rank=rank,
                score=round(fused[i], 5),
                path=meta[i].get("path", ""),
                line=int(meta[i].get("line", 0) or 0),
                language=_lang_of(meta[i]),
                chunk_type=meta[i].get("chunk_type", ""),
                symbol=meta[i].get("symbol", ""),
                text=meta[i].get("text", ""),
                dense_score=round(dense_score.get(i, 0.0), 4),
                bm25_score=round(bm_score.get(i, 0.0), 4),
                flagged_injection=flagged[i],
            )
            for rank, i in enumerate(order, 1)
        ]

        # Abstention signal (advisory; calibrated by the eval harness). Gate on the
        # dense score, with an exact symbol match (high precision) as the only
        # override. BM25 is deliberately NOT an override: it fires on common words
        # ("how", "create") and would let off-topic queries through.
        top_dense = max(dense_score.values()) if dense_score else 0.0
        sym_hit = bool(sym_ranked)
        insufficient = top_dense < config.DENSE_FLOOR and not sym_hit
        confidence = round(min(max(top_dense, 0.0), 1.0), 3)

        notes: List[str] = []
        if insufficient:
            notes.append(
                "No strongly relevant Chrono content found. Include a class/function "
                "name or the exact error message, or update the index."
            )

        return Retrieval(
            query=query,
            results=results,
            insufficient_evidence=insufficient,
            confidence=confidence,
            version_label=self.version_label,
            notes=notes,
        )
