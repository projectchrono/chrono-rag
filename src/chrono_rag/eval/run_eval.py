r"""Retrieval evaluation harness.

Runs the gold set through the retrieval core and reports recall@k, MRR (over
positive queries), and abstention behavior on negatives. Also sweeps the dense
floor to recommend a calibrated abstention threshold.

Run:
  python -m chrono_rag.eval.run_eval            # uses the default index
  CHRONO_RAG_INDEX=... python -m chrono_rag.eval.run_eval
Exit code is non-zero if metrics fall below the gates (for CI).

Gold entries may carry `"channels": ["main"]` to apply only to indexes of
those channels (manifest `channel`): content that exists on Chrono's main
branch but not in the 10.0.0 release must not count as a miss (or a wrongful
abstention) against the release index. Entries without `channels` apply to
every index.
"""
from __future__ import annotations

import json
import os

from chrono_rag.core import config
from chrono_rag.core.retrieval import RetrievalCore

K = 8
GOLD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gold.jsonl")

# CI gates (loose; tighten as the gold set grows).
MIN_RECALL = 0.80
MIN_NEG_ABSTAIN = 0.66


def load_gold():
    items = []
    with open(GOLD, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def first_hit_rank(results, relevant):
    for res in results:
        p = res.path.lower()
        if any(sub in p for sub in relevant):
            return res.rank
    return None


def applies(item, channel) -> bool:
    chans = item.get("channels")
    if not chans:
        return True
    return channel is not None and channel in chans


def main() -> int:
    core = RetrievalCore()
    channel = core.store.manifest.get("channel")
    gold_all = load_gold()
    gold = [g for g in gold_all if applies(g, channel)]
    skipped = len(gold_all) - len(gold)

    positives = [g for g in gold if g["kind"] != "negative"]
    negatives = [g for g in gold if g["kind"] == "negative"]

    recall_hits = 0
    mrr = 0.0
    pos_abstained = 0
    rows = []
    confidences = []  # (confidence, is_positive)

    for g in positives:
        r = core.search(g["query"], k=K)
        rank = first_hit_rank(r.results, g["relevant"])
        if rank is not None:
            recall_hits += 1
            mrr += 1.0 / rank
        if r.insufficient_evidence:
            pos_abstained += 1
        confidences.append((r.confidence, True))
        top = r.results[0].path if r.results else "-"
        rows.append((g["query"][:46], r.confidence, rank or 0, r.insufficient_evidence, top))

    neg_abstained = 0
    for g in negatives:
        r = core.search(g["query"], k=K)
        if r.insufficient_evidence:
            neg_abstained += 1
        confidences.append((r.confidence, False))
        rows.append((g["query"][:46], r.confidence, 0, r.insufficient_evidence, "(negative)"))

    n_pos = len(positives)
    recall = recall_hits / n_pos if n_pos else 0.0
    mrr = mrr / n_pos if n_pos else 0.0
    neg_abstain_rate = neg_abstained / len(negatives) if negatives else 1.0

    print(f"index: {len(core.store)} chunks, model={core.store.model_name}, "
          f"chrono={core.store.manifest.get('chrono_version')}, channel={channel}, "
          f"floor={config.DENSE_FLOOR}")
    print(f"scope: {core.version_label}; gold entries used: {len(gold)}"
          + (f" ({skipped} skipped: other channels)" if skipped else ""))
    print("-" * 78)
    print(f"{'query':46} {'conf':>5} {'rank':>4} {'abstain':>7}  top")
    for q, c, rank, ab, top in rows:
        print(f"{q:46} {c:5.3f} {rank:4d} {str(ab):>7}  {top}")
    print("-" * 78)
    print(f"recall@{K} (positives): {recall:.2f}   MRR: {mrr:.3f}   "
          f"positives wrongly abstaining: {pos_abstained}/{n_pos}")
    print(f"negative abstain rate: {neg_abstain_rate:.2f} ({neg_abstained}/{len(negatives)})")

    # Dense-floor sweep: where do positives and negatives separate?
    print("\nfloor sweep (approx, dense-only):")
    print(f"{'floor':>6} {'neg-abstain':>11} {'pos-wrong':>9}")
    for i in range(50, 82, 2):
        floor = i / 100.0
        neg_ab = sum(1 for c, pos in confidences if not pos and c < floor)
        pos_wrong = sum(1 for c, pos in confidences if pos and c < floor)
        print(f"{floor:6.2f} {neg_ab:>5}/{len(negatives):<5} {pos_wrong:>4}/{n_pos:<4}")

    ok = recall >= MIN_RECALL and neg_abstain_rate >= MIN_NEG_ABSTAIN and pos_abstained == 0
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
