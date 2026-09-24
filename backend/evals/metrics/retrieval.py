"""Retrieval metrics over ranked chunk ids. Pure functions, no LLM calls.

Every function returns None when the case has no relevant chunks (unanswerable / chitchat):
those cases are "not applicable" for retrieval, and must not be counted as 0 or 1.
"""
import math
from collections.abc import Sequence


def _rel(retrieved: Sequence[str], relevant: set[str], k: int) -> list[bool]:
    return [cid in relevant for cid in retrieved[:k]]


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    return sum(_rel(retrieved, relevant, k)) / len(relevant)


def precision_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    return sum(_rel(retrieved, relevant, k)) / k


def hit_rate_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    return 1.0 if any(_rel(retrieved, relevant, k)) else 0.0


def reciprocal_rank(retrieved: Sequence[str], relevant: set[str]) -> float | None:
    """1/rank of the first relevant chunk (0.0 if none retrieved). Averaged over cases this is MRR."""
    if not relevant:
        return None
    for rank, cid in enumerate(retrieved, start=1):
        if cid in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float | None:
    """Binary-relevance nDCG@k."""
    if not relevant:
        return None
    gains = _rel(retrieved, relevant, k)
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg
