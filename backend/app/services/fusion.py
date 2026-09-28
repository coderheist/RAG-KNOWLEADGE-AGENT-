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


def pin(ids: list[str], pinned: str, window: int) -> list[str]:
    """
    Ensure ``pinned`` is within the first ``window`` ids, taking the window's last slot if it is not already
    there. RRF rewards chunks that are mediocre in *both* lists over one that is first in only one list; for an
    exact identifier the BM25 leader is usually the answer, so it must not be fused out of the top-k.
    """
    if window <= 0 or pinned in ids[:window]:
        return ids
    rest = [i for i in ids if i != pinned]
    return [*rest[: window - 1], pinned, *rest[window - 1 :]]
