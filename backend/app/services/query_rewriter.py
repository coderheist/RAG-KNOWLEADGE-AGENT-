"""
Query rewriting (Phase 2).

Turns a context-dependent follow-up ("what are his skills?") into a standalone search query
("What are Marcus Bell's technical skills?") *before* retrieval, so the retriever embeds a
question that actually names its subject.

Uses the Gemini SDK directly rather than a LangChain chat model: inside the graph, LangChain
models emit ``on_chat_model_stream`` events that would leak into the user-facing answer stream.

A bad rewrite must never break retrieval: any failure or implausible output falls back to the
original query.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.services.metrics import record_sdk_usage
from app.utils.logging import get_logger

logger = get_logger(__name__)

RewriteLLM = Callable[[str], Awaitable[str]]

_INSTRUCTION = (
    "Rewrite the user's latest question into a single self-contained search query that resolves every "
    "pronoun and implicit reference using the conversation. Keep the user's own terminology. "
    "Output only the rewritten query, with no preamble, quotes or explanation."
)

# A model that explains instead of answering usually opens with one of these.
_PREAMBLES = ("here", "sure", "okay", "ok,", "rewritten", "standalone", "the rewritten", "search query",
              "query:", "i ", "i'", "as an ai", "note:", "the user")

_MAX_GROWTH_FACTOR = 3
_MIN_ALLOWED_LENGTH = 200   # short pronoun questions legitimately grow by more than 3x


def _text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content)


def format_history(history: list[BaseMessage], turns: int) -> str:
    """The last ``turns`` user/assistant exchanges, one line per message, long answers truncated."""
    recent = [m for m in history if isinstance(m, (HumanMessage, AIMessage))][-2 * turns:]
    lines = []
    for m in recent:
        role = "User" if isinstance(m, HumanMessage) else "Assistant"
        lines.append(f"{role}: {_text(m)[:400]}")
    return "\n".join(lines)


def build_prompt(query: str, history: list[BaseMessage], turns: int) -> str:
    conversation = format_history(history, turns)
    return f"{_INSTRUCTION}\n\nConversation:\n{conversation}\n\nLatest question: {query}\n\nRewritten query:"


def guard_rewrite(original: str, candidate: str) -> str | None:
    """Return the cleaned rewrite, or None if it is empty, too long, multi-line, or an explanation."""
    text = candidate.strip().strip("`\"'").strip()
    if not text or "\n" in text:
        return None
    if len(text) > max(_MAX_GROWTH_FACTOR * len(original), _MIN_ALLOWED_LENGTH):
        return None
    if text.lower().startswith(_PREAMBLES):
        return None
    return text


async def rewrite_query(
    query: str, history: list[BaseMessage], llm: RewriteLLM, turns: int = 3
) -> tuple[str, bool]:
    """Return ``(search_query, rewrite_applied)``. No history means no LLM call and no added latency."""
    if not history:
        return query, False
    try:
        raw = await llm(build_prompt(query, history, turns))
    except Exception as exc:  # any provider failure must degrade to the old behaviour
        logger.warning("Query rewrite failed, using original query: %s", exc)
        return query, False
    cleaned = guard_rewrite(query, raw)
    if cleaned is None:
        logger.warning("Query rewrite rejected by guard (%r), using original query", raw[:120])
        return query, False
    return cleaned, cleaned != query


def gemini_rewrite_llm(model: str, api_key: str, max_output_tokens: int) -> RewriteLLM:
    """A RewriteLLM backed by the Gemini SDK (temperature 0, small output cap)."""

    def call(prompt: str) -> str:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        response = genai.GenerativeModel(model).generate_content(
            prompt, generation_config={"temperature": 0, "max_output_tokens": max_output_tokens}
        )
        record_sdk_usage(model, "rewrite", response)
        return response.text

    async def llm(prompt: str) -> str:
        return await asyncio.to_thread(call, prompt)

    return llm
