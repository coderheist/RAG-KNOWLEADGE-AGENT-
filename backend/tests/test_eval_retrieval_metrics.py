"""Hand-computed checks for evals.metrics.retrieval."""
import math

import pytest

from evals.metrics.retrieval import hit_rate_at_k, ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank

RETRIEVED = ["a", "b", "c", "d"]
RELEVANT = {"b", "c"}


def test_recall_at_k() -> None:
    assert recall_at_k(RETRIEVED, RELEVANT, 1) == 0.0
    assert recall_at_k(RETRIEVED, RELEVANT, 2) == 0.5
    assert recall_at_k(RETRIEVED, RELEVANT, 3) == 1.0


def test_precision_at_k() -> None:
    assert precision_at_k(RETRIEVED, RELEVANT, 3) == pytest.approx(2 / 3)
    assert precision_at_k(RETRIEVED, RELEVANT, 4) == 0.5


def test_hit_rate_at_k() -> None:
    assert hit_rate_at_k(RETRIEVED, RELEVANT, 1) == 0.0
    assert hit_rate_at_k(RETRIEVED, RELEVANT, 2) == 1.0


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(RETRIEVED, RELEVANT) == 0.5
    assert reciprocal_rank(["x", "y"], RELEVANT) == 0.0


def test_ndcg_at_k() -> None:
    dcg = 1 / math.log2(3) + 1 / math.log2(4)
    idcg = 1 / math.log2(2) + 1 / math.log2(3)
    assert ndcg_at_k(RETRIEVED, RELEVANT, 3) == pytest.approx(dcg / idcg)
    assert ndcg_at_k(["b", "c"], RELEVANT, 2) == pytest.approx(1.0)


def test_no_relevant_chunks_is_not_applicable() -> None:
    assert recall_at_k(RETRIEVED, set(), 5) is None
    assert precision_at_k(RETRIEVED, set(), 5) is None
    assert hit_rate_at_k(RETRIEVED, set(), 5) is None
    assert reciprocal_rank(RETRIEVED, set()) is None
    assert ndcg_at_k(RETRIEVED, set(), 5) is None


def test_empty_retrieval_scores_zero_not_none() -> None:
    assert recall_at_k([], RELEVANT, 5) == 0.0
    assert reciprocal_rank([], RELEVANT) == 0.0
