"""In-process BM25 lexical index.

The dense embedder is weak on exact identifiers (e.g. `ChLinkMotorRotationSpeed`,
`SetChronoDataPath`). BM25 over a code-aware tokenization recovers those. Built
in memory at load time; fast at this corpus scale.
"""
from __future__ import annotations

import re
from typing import List, Tuple

import numpy as np

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def tokenize(text: str) -> List[str]:
    """Lowercase word tokens, plus camelCase/snake_case sub-parts so symbol
    fragments are searchable (e.g. `ChLinkTSDA` -> ch, link, tsda)."""
    toks: List[str] = []
    for raw in _TOKEN_RE.findall(text):
        low = raw.lower()
        toks.append(low)
        parts: List[str] = []
        for seg in raw.split("_"):
            parts.extend(_CAMEL_BOUNDARY.sub(" ", seg).split())
        for p in parts:
            pl = p.lower()
            if pl and pl != low:
                toks.append(pl)
    return toks


class BM25Index:
    def __init__(self, texts: List[str]) -> None:
        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:  # pragma: no cover - install-time guard
            raise ImportError(
                "rank-bm25 is required for lexical search. "
                "Install it with `pip install rank-bm25`."
            ) from exc
        self._bm25 = BM25Okapi([tokenize(t) for t in texts])

    def search(self, query: str, k: int) -> List[Tuple[int, float]]:
        """Top-k by BM25 score; drops zero-score (no lexical overlap) hits."""
        scores = self._bm25.get_scores(tokenize(query))
        k = max(1, min(int(k), len(scores)))
        idx = np.argpartition(-scores, k - 1)[:k]
        idx = idx[np.argsort(-scores[idx])]
        return [(int(i), float(scores[i])) for i in idx if scores[i] > 0.0]
