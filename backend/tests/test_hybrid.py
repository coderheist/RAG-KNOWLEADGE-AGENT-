"""Unit tests for hybrid search fusion and the hybrid retrieval pipeline. No network, no models."""
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.services import retrieval_service
from app.services.fusion import reciprocal_rank_fusion


def test_rrf_matches_hand_computed_scores() -> None:
    fused = dict(reciprocal_rank_fusion([["a", "b"], ["b", "c"]], k=60))
    assert fused["a"] == pytest.approx(1 / 61)
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert fused["c"] == pytest.approx(1 / 62)


def test_rrf_orders_by_score_and_breaks_ties_on_id() -> None:
    assert [i for i, _ in reciprocal_rank_fusion([["a", "b"], ["b", "c"]])] == ["b", "a", "c"]
    assert [i for i, _ in reciprocal_rank_fusion([["x"], ["y"]])] == ["x", "y"]


def test_rrf_single_ranking_preserves_order() -> None:
    assert [i for i, _ in reciprocal_rank_fusion([["p", "q", "r"]])] == ["p", "q", "r"]


def test_hybrid_enabled_requires_flag_and_a_collection_with_sparse_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import vector_service

    monkeypatch.setattr(vector_service, "_hybrid_supported", {"with_sparse": True, "dense_only": False})
    on = SimpleNamespace(ENABLE_HYBRID_SEARCH=True, QDRANT_COLLECTION="with_sparse")
    off = SimpleNamespace(ENABLE_HYBRID_SEARCH=False, QDRANT_COLLECTION="with_sparse")
    assert vector_service.hybrid_enabled(on) is True
    assert vector_service.hybrid_enabled(off) is False
    assert vector_service.hybrid_enabled(on, "dense_only") is False       # old collection: fall back to dense
    assert vector_service.hybrid_enabled(on, "never_seen") is False


@dataclass
class FakeHit:
    id: str
    score: float
    payload: dict


@dataclass
class FakeRecord:
    id: str
    vector: list[float]


class FakeClient:
    def __init__(self, dense: list[FakeHit], sparse: list[FakeHit], vectors: dict[str, list[float]]) -> None:
        self.dense, self.sparse, self.vectors = dense, sparse, vectors

    async def search(self, collection_name, query_vector, limit, with_payload):
        return self.dense if isinstance(query_vector, list) else self.sparse

    async def retrieve(self, collection_name, ids, with_vectors, with_payload):
        return [FakeRecord(id=i, vector=self.vectors[i]) for i in ids]


def hit(cid: str, score: float, text: str) -> FakeHit:
    return FakeHit(id=cid, score=score, payload={"text": text})


def settings(**overrides):
    base = dict(CANDIDATE_MULTIPLIER=4, ENABLE_HYBRID_SEARCH=True, ENABLE_RERANKING=False, RRF_K=60,
                RERANK_CANDIDATE_COUNT=20)
    return SimpleNamespace(**{**base, **overrides})


@pytest.fixture(autouse=True)
def stub_sparse_query(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_embed_query(text: str):
        return SimpleNamespace(indices=[1], values=[1.0])

    monkeypatch.setattr(retrieval_service.sparse, "embed_query", fake_embed_query)
    monkeypatch.setattr(retrieval_service.qmodels, "NamedSparseVector", lambda name, vector: ("sparse", name, vector))


async def test_hybrid_fuses_dense_and_sparse_and_scores_sparse_only_hits() -> None:
    client = FakeClient(
        dense=[hit("a", 0.9, "alpha"), hit("b", 0.8, "beta")],
        sparse=[hit("b", 7.0, "beta"), hit("c", 5.0, "gamma")],
        vectors={"c": [0.0, 1.0]},
    )
    hits = await retrieval_service._hybrid_candidates(client, "docs", "q", [1.0, 1.0], 3, settings())
    assert [h.id for h in hits] == ["b", "a", "c"]
    assert hits[0].score == 0.8                                   # dense cosine kept for dense hits
    assert hits[2].score == pytest.approx(1 / 2 ** 0.5)           # cosine([1,1], [0,1]) for the sparse-only hit
    assert all(h.rerank_score is None for h in hits)


async def test_rerank_reorders_candidates_and_carries_the_score(monkeypatch: pytest.MonkeyPatch) -> None:
    class LongestFirst:
        def rerank(self, query: str, documents: list[str]) -> list[float]:
            return [float(len(d)) for d in documents]

    monkeypatch.setattr(retrieval_service, "get_reranker", lambda: LongestFirst())
    client = FakeClient(
        dense=[hit("a", 0.9, "aa"), hit("b", 0.8, "bbbb"), hit("c", 0.7, "c")], sparse=[], vectors={}
    )
    hits = await retrieval_service._hybrid_candidates(
        client, "docs", "q", [1.0], 2, settings(ENABLE_HYBRID_SEARCH=False, ENABLE_RERANKING=True)
    )
    assert [h.id for h in hits] == ["b", "a"]                     # top_k after reranking
    assert [h.rerank_score for h in hits] == [4.0, 2.0]
    assert hits[0].score == 0.8                                   # cosine stays available beside the rerank score


async def test_reranker_failure_falls_back_to_fused_order(monkeypatch: pytest.MonkeyPatch) -> None:
    class Broken:
        def rerank(self, query: str, documents: list[str]) -> list[float]:
            raise RuntimeError("model failed to load")

    monkeypatch.setattr(retrieval_service, "get_reranker", lambda: Broken())
    client = FakeClient(dense=[hit("a", 0.9, "aa"), hit("b", 0.8, "bb")], sparse=[], vectors={})
    hits = await retrieval_service._hybrid_candidates(
        client, "docs", "q", [1.0], 2, settings(ENABLE_HYBRID_SEARCH=False, ENABLE_RERANKING=True)
    )
    assert [h.id for h in hits] == ["a", "b"]
    assert all(h.rerank_score is None for h in hits)
