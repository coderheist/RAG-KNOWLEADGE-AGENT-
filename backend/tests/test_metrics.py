"""Unit tests for Prometheus metrics (Phase 6): token/cost accounting and the scrape format."""
from types import SimpleNamespace

import pytest
from prometheus_client import generate_latest

from app.services import metrics


def _sample(name: str, labels: dict) -> float:
    from prometheus_client import REGISTRY
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_record_llm_usage_counts_tokens_and_cost(monkeypatch) -> None:
    monkeypatch.setattr(
        metrics, "get_settings", lambda: SimpleNamespace(LLM_PRICE_INPUT_PER_MTOK=0.10, LLM_PRICE_OUTPUT_PER_MTOK=0.40)
    )
    labels = {"model": "m-test", "step": "generate", "kind": "input"}
    before_in = _sample("rag_llm_tokens_total", labels)
    before_cost = _sample("rag_llm_cost_usd_total", {"model": "m-test"})

    cost = metrics.record_llm_usage("m-test", "generate", 1_000_000, 500_000)

    assert cost == pytest.approx(0.30)
    assert _sample("rag_llm_tokens_total", labels) - before_in == 1_000_000
    assert abs(_sample("rag_llm_cost_usd_total", {"model": "m-test"}) - before_cost - 0.30) < 1e-9


def test_sdk_usage_without_metadata_is_ignored() -> None:
    metrics.record_sdk_usage("m-none", "agent", object())          # must not raise
    assert _sample("rag_llm_tokens_total", {"model": "m-none", "step": "agent", "kind": "input"}) == 0.0


def test_scrape_output_names_every_metric() -> None:
    text = generate_latest().decode()
    for name in ("rag_queries_total", "rag_query_seconds", "rag_stage_seconds", "rag_llm_tokens_total",
                 "rag_embedding_rate_limited_total", "rag_ingested_chunks_total"):
        assert name in text
