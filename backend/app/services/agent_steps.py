"""
Decision steps for the agentic RAG graph (Phase 4).

Each step takes an injectable structured-output LLM and fails open: if the model errors or returns something
unusable, the step returns the choice that reproduces the old linear pipeline (retrieve, keep every chunk,
no caveat). A flaky helper model must never make answers worse than the pipeline without it.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from app.services.llm_json import StructuredLLM
from app.services.query_rewriter import format_history
from app.services.sparse import IDENTIFIER
from app.utils.logging import get_logger

logger = get_logger(__name__)

Route = Literal["needs_retrieval", "chitchat", "clarification_needed"]
Grade = Literal["relevant", "partial", "irrelevant"]

UNGROUNDED_CAVEAT = "\n\n_Note: parts of this answer may not be fully supported by the retrieved documents._"


class RouteDecision(BaseModel):
    route: Route


class GradeResult(BaseModel):
    grades: list[Grade]


class Groundedness(BaseModel):
    grounded: bool
    unsupported_claims: list[str] = Field(default_factory=list)


# ── Router ────────────────────────────────────────────────────────────────────────────────────

_ROUTER_PROMPT = """Classify the user's latest message for a document question-answering assistant. Reply with JSON only:
{{"route": "needs_retrieval" | "chitchat" | "clarification_needed"}}

- needs_retrieval: any question or request that could be answered from documents, including follow-ups that
  refer back to earlier questions ("what are his skills?", "and its price?").
- chitchat: greetings, thanks, farewells, small talk, questions about the assistant itself, or a request to
  repeat or rephrase the assistant's previous message. These need no document lookup.
- clarification_needed: the message is too vague to search for and nothing in the conversation says what it
  refers to ("what about it?" as the first message).
When in doubt, choose needs_retrieval.

Conversation so far:
{history}

Latest message: {query}"""


async def classify_turn(query: str, history: list[BaseMessage], llm: StructuredLLM) -> Route:
    prompt = _ROUTER_PROMPT.format(history=format_history(history, 2) or "(none)", query=query)
    try:
        return (await llm(prompt, RouteDecision)).route
    except Exception as exc:
        logger.warning("Router failed, defaulting to retrieval: %s", exc)
        return "needs_retrieval"


# ── Chunk grading + retry policy ──────────────────────────────────────────────────────────────

_GRADER_PROMPT = """Grade how well each numbered passage helps answer the question. Reply with JSON only:
{{"grades": ["relevant" | "partial" | "irrelevant", ...]}} with exactly {n} entries, in passage order.

- relevant: contains information that directly answers the question.
- partial: related and useful context, but does not answer it by itself.
- irrelevant: about something else (a different product, person, or topic).

Question: {query}

{passages}"""


async def grade_chunks(query: str, chunk_texts: list[str], llm: StructuredLLM) -> list[Grade]:
    """One batched call. On any failure or a wrong-length answer, every chunk is treated as relevant."""
    if not chunk_texts:
        return []
    passages = "\n\n".join(f"[{i}] {text[:600]}" for i, text in enumerate(chunk_texts, 1))
    prompt = _GRADER_PROMPT.format(n=len(chunk_texts), query=query, passages=passages)
    try:
        grades = (await llm(prompt, GradeResult)).grades
    except Exception as exc:
        logger.warning("Chunk grading failed, keeping all chunks: %s", exc)
        return ["relevant"] * len(chunk_texts)
    if len(grades) != len(chunk_texts):
        logger.warning("Grader returned %d grades for %d chunks, keeping all", len(grades), len(chunk_texts))
        return ["relevant"] * len(chunk_texts)
    return grades


def is_weak(grades: list[Grade], min_relevant: int) -> bool:
    """
    Retrieval is weak when fewer than ``min_relevant`` chunks are graded *relevant* (partials are extra
    context, not evidence). A single-fact answer lives in one chunk, so the default is 1: a higher value
    makes nearly every single-fact question retry needlessly.
    """
    return grades.count("relevant") < min_relevant


def should_retry(weak: bool, retrieval_attempts: int, max_loops: int) -> bool:
    """``retrieval_attempts`` counts retrievals already done; at most ``max_loops`` retries follow the first."""
    return weak and retrieval_attempts <= max_loops


def select_from_pool(pool: list[tuple[str, str]], top_k: int) -> list[str]:
    """
    Pick the chunk ids to generate from, across every retrieval attempt (``pool`` is ``(chunk_id, grade)`` in
    retrieval order). Relevant chunks come first, then partial ones. If the grader found nothing usable, fall
    back to everything retrieved: the generator can still refuse, but it cannot answer from chunks it never
    sees, and graders do misjudge look-alike identifiers.
    """
    seen: dict[str, str] = {}
    for cid, grade in pool:
        if cid not in seen or grade == "relevant":
            seen[cid] = grade
    ranked = [c for c, g in seen.items() if g == "relevant"] + [c for c, g in seen.items() if g == "partial"]
    return (ranked or list(seen))[:top_k]




def keep_identifiers(original: str, candidate: str) -> str:
    """Re-append identifiers (error codes, SKUs, versions) the retry rewrite dropped: they are what search needs."""
    missing = [t for t in IDENTIFIER.findall(original) if t.lower() not in candidate.lower()]
    return " ".join([candidate, *missing]) if missing else candidate


_RETRY_INSTRUCTION = (
    "The previous search queries did not find relevant passages. Write ONE different search query for the "
    "same information need: rephrase it with different wording, or make it broader. Keep proper names and "
    "identifiers exactly. Output only the query, with no preamble, quotes or explanation."
)


def build_retry_prompt(query: str, history: list[BaseMessage], failed_queries: list[str], turns: int = 3) -> str:
    tried = "\n".join(f"- {q}" for q in failed_queries)
    conversation = format_history(history, turns) or "(none)"
    return (
        f"{_RETRY_INSTRUCTION}\n\nConversation:\n{conversation}\n\nUser's question: {query}\n\n"
        f"Queries that already failed:\n{tried}\n\nNew search query:"
    )


# ── Groundedness ──────────────────────────────────────────────────────────────────────────────

_GROUNDED_PROMPT = """Check whether every factual claim in the ANSWER is supported by the PASSAGES. Reply with JSON only:
{{"grounded": true | false, "unsupported_claims": ["..."]}}
Mark grounded=false only if the answer states specific facts that no passage supports or that a passage
contradicts. Refusals ("the documents do not say") and restatements of the question are grounded.

PASSAGES:
{passages}

ANSWER:
{answer}"""


async def check_groundedness(answer: str, chunk_texts: list[str], llm: StructuredLLM) -> Groundedness | None:
    """None when the check itself failed: unknown is reported as unknown, never as a false alarm."""
    passages = "\n\n".join(f"[{i}] {text[:1500]}" for i, text in enumerate(chunk_texts, 1))
    try:
        return await llm(_GROUNDED_PROMPT.format(passages=passages, answer=answer), Groundedness)
    except Exception as exc:
        logger.warning("Groundedness check failed: %s", exc)
        return None
