"""
Langfuse tracing (Phase 6): one trace per query, a span per graph node, tagged with the active feature flags.

Off unless LANGFUSE_ENABLED and both keys are set. Tracing must never break a query, so every call here
fails open (logs a warning, returns None). The self-hosted Langfuse comes up with
`docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d`.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import Settings, get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

FLAGS = (
    "ENABLE_QUERY_REWRITE", "ENABLE_HYBRID_SEARCH", "ENABLE_RERANKING", "ENABLE_AGENTIC_LOOP",
    "ENABLE_GROUNDEDNESS_CHECK", "ENABLE_VERIFIED_CITATIONS",
)


def active_flags(settings: Settings) -> dict[str, Any]:
    """Feature flags plus the model, as recorded on traces and feedback rows."""
    return {**{flag: getattr(settings, flag, None) for flag in FLAGS}, "GEMINI_MODEL": settings.GEMINI_MODEL}


@lru_cache
def _client() -> Any:
    from langfuse import Langfuse

    s = get_settings()
    return Langfuse(public_key=s.LANGFUSE_PUBLIC_KEY, secret_key=s.LANGFUSE_SECRET_KEY, host=s.LANGFUSE_HOST)


def start_trace(query: str, conversation_id: str) -> Any | None:
    """A Langfuse trace for one /query, or None when tracing is off or unavailable."""
    s = get_settings()
    if not (s.LANGFUSE_ENABLED and s.LANGFUSE_PUBLIC_KEY and s.LANGFUSE_SECRET_KEY):
        return None
    try:
        flags = active_flags(s)
        tags = [f"{k.removeprefix('ENABLE_').lower()}:{'on' if v else 'off'}" for k, v in flags.items() if k in FLAGS]
        return _client().trace(
            name="rag_query", session_id=conversation_id, input=query, tags=tags, metadata=flags
        )
    except Exception as exc:
        logger.warning("Langfuse trace not started: %s", exc)
        return None


def langchain_callbacks(trace: Any | None) -> list[Any]:
    """LangChain/LangGraph callback that records every node as a span under ``trace``."""
    if trace is None:
        return []
    try:
        return [trace.get_langchain_handler(update_parent=False)]
    except Exception as exc:
        logger.warning("Langfuse handler unavailable: %s", exc)
        return []


def end_trace(trace: Any | None, output: str, metadata: dict[str, Any]) -> None:
    if trace is None:
        return
    try:
        trace.update(output=output, metadata=metadata)
    except Exception as exc:
        logger.warning("Langfuse trace not finalised: %s", exc)
