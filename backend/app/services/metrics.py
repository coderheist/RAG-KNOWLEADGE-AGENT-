"""
Prometheus metrics (Phase 6), scraped at GET /metrics.

Replaces the old in-process singleton: counters and histograms here survive per process and are aggregated by
Prometheus across restarts and replicas. Label values are small closed sets (routes, stages, steps) so the
series count stays bounded.
"""
from prometheus_client import Counter, Histogram

from app.config import get_settings

QUERIES = Counter("rag_queries_total", "Queries by route and outcome", ["route", "outcome"])
QUERY_SECONDS = Histogram(
    "rag_query_seconds", "End-to-end /query latency", ["route"], buckets=(0.5, 1, 2, 3, 5, 8, 13, 20, 30, 60, 120)
)
RETRIEVAL_ATTEMPTS = Histogram(
    "rag_retrieval_attempts", "Retrievals per query (1 = no retry)", buckets=(1, 2, 3, 4)
)
STAGE_SECONDS = Histogram(
    "rag_stage_seconds", "Retrieval stage latency", ["stage"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
LLM_TOKENS = Counter("rag_llm_tokens_total", "LLM tokens by model, step and direction", ["model", "step", "kind"])
LLM_COST = Counter("rag_llm_cost_usd_total", "LLM cost from the configured per-token prices", ["model"])

EMBED_REQUESTS = Counter("rag_embedding_requests_total", "Embedding API attempts (including retries)")
EMBED_RATE_LIMITED = Counter("rag_embedding_rate_limited_total", "Embedding attempts rejected with HTTP 429")
EMBED_RETRIES = Counter("rag_embedding_retries_total", "Embedding retries performed")
EMBED_FAILURES = Counter("rag_embedding_failures_total", "Embedding batches that failed after all retries")

INGESTED_DOCUMENTS = Counter("rag_ingested_documents_total", "Documents processed by outcome", ["status"])
INGESTED_CHUNKS = Counter("rag_ingested_chunks_total", "Chunks indexed")


def record_llm_usage(model: str, step: str, input_tokens: int, output_tokens: int) -> float:
    """Count tokens and add their cost at the configured prices (USD per 1M tokens; 0 on the free tier)."""
    settings = get_settings()
    LLM_TOKENS.labels(model, step, "input").inc(input_tokens)
    LLM_TOKENS.labels(model, step, "output").inc(output_tokens)
    cost = (input_tokens * settings.LLM_PRICE_INPUT_PER_MTOK + output_tokens * settings.LLM_PRICE_OUTPUT_PER_MTOK) / 1e6
    LLM_COST.labels(model).inc(cost)
    return cost


def record_sdk_usage(model: str, step: str, response: object) -> None:
    """Token usage from a google-generativeai response; missing metadata is ignored, never an error."""
    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        record_llm_usage(
            model, step, getattr(usage, "prompt_token_count", 0) or 0, getattr(usage, "candidates_token_count", 0) or 0
        )
