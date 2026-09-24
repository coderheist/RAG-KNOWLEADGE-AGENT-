"""Rank fusion for hybrid search (Phase 3)."""

from collections.abc import Sequence


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], k: int = 60) -> list[tuple[str, float]]:
    """
    Merge several ranked id lists: ``RRF(d) = sum_i 1 / (k + rank_i(d))`` with 1-based ranks.

    Needs no score normalisation between retrievers, which is why it is the standard fusion for
    mixing dense cosine scores with BM25 scores. Ties break on id so the output is deterministic.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
