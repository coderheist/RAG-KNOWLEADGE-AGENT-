"""
LangGraph RAG agent (Phase 4).

Graph topology:
    START → router ─┬─ needs_retrieval → rewrite_query → retrieve → [grade_chunks ─ weak, ≤ MAX loops ─┐]
                    │                        ▲                                                       │
                    │                        └───────────────────────────────────────────────────────┘
                    │                   → generate → check_grounded → save_history → END
                    └─ chitchat / clarification_needed → direct_response → save_history → END
    (grade_chunks, the router's LLM call and check_grounded are passthroughs unless the agentic flags are on)

Streaming:
    The graph is executed via ``graph.astream_events(input, version="v2")``.
    The ``generate`` node uses a streaming-enabled ChatGoogleGenerativeAI,
    so LangChain emits ``on_chat_model_stream`` events for every token.
    The ``retrieve`` node's output is surfaced via ``on_chain_end`` events.

Conversation memory:
    History is loaded *before* the graph runs (it requires DB I/O that is
    cleaner outside the graph) and injected into the initial state.
    The ``save_history`` node persists the user+assistant turn after the
    answer is fully assembled.
"""

from __future__ import annotations

import time
import uuid
from typing import AsyncGenerator, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph

from app.config import get_settings
from app.services import metrics, tracing
from app.services.agent_steps import (
    UNGROUNDED_CAVEAT,
    build_retry_prompt,
    check_groundedness,
    classify_turn,
    grade_chunks,
    is_weak,
    keep_identifiers,
    select_from_pool,
    should_retry,
)
from app.services.citations import (
    STRUCTURED_OUTPUT_INSTRUCTIONS,
    AnswerStreamExtractor,
    find_invalid_inline_citations,
    parse_structured_answer,
    validate_claims,
)
from app.services.conversation_service import save_turn
from app.services.llm_json import gemini_structured_llm
from app.services.query_rewriter import gemini_rewrite_llm, guard_rewrite, rewrite_query
from app.services.retrieval_service import RetrievedChunk, get_stage_timings, retrieve_chunks
from app.utils.logging import get_logger

logger = get_logger(__name__)


# ── RAG system prompt ─────────────────────────────────────────────────────────

_SYSTEM_TEMPLATE = """\
You are an Enterprise RAG Assistant with access to a private document knowledge base.

CRITICAL RULES — violating any of these is an error:

1. ANSWER ONLY THE CURRENT QUESTION.
   Do NOT preface your answer with a summary or recap of what you said in
   previous turns. Start your response with the answer to the current question.

2. USE RETRIEVED DOCUMENTS as the primary source of truth.
   Never invent facts that are not present in the retrieved context.

3. USE CONVERSATION HISTORY ONLY for coreference resolution.
   History lets you resolve pronouns like "he", "she", "it", "them",
   or phrases like "that project", "those skills", "previous answer".
   DO NOT repeat, summarise, or reference prior answers beyond what is
   strictly needed to understand the current question.

4. REPEAT-REQUEST RULE: If the user says "list them again", "show as bullet
   points", "repeat that", or similar — output ONLY that specific list or
   item. Do not add any other information.

5. BE CONCISE. Do not add context, background, or related information
   unless the user explicitly asks for it.

6. CITE SOURCES inline: (filename.pdf, p. N) when using retrieved text.

7. If the retrieved context does not answer the question, say so clearly.
   Do not guess.

── Retrieved context ───────────────────────────────────────────────────────────────
{context}
──────────────────────────────────────────────────────────────────────────────
"""


# ── Graph state ───────────────────────────────────────────────────────────────

class RAGState(TypedDict):
    """Shared mutable state threaded through every node in the graph."""

    query: str
    search_query: str              # standalone query used for retrieval (== query when no rewrite)
    rewrite_applied: bool          # for tracing and evals
    conversation_id: str           # always a str; uuid.UUID is not JSON-serialisable
    history_messages: list[BaseMessage]
    top_k: int
    chunks: list[RetrievedChunk]
    sources: list[dict]            # serialisable dicts ready for SSE
    timings_ms: dict[str, float]   # per-stage retrieval timings (search / fuse / rerank)
    route: str                     # needs_retrieval | chitchat | clarification_needed
    retrieval_attempt: int         # retrievals performed so far; capped by MAX_RETRIEVAL_LOOPS
    retrieval_weak: bool           # the last grading found too few usable chunks
    chunk_grades: list[str]        # relevant | partial | irrelevant, per chunk of the last retrieval
    pool: list                     # (RetrievedChunk, grade) from every attempt; the final context is chosen here
    failed_queries: list[str]      # search queries that retrieved weakly, fed to the retry rewrite
    groundedness: dict             # {"grounded": bool, "unsupported_claims": [...]} once checked
    structured: bool               # the answer came from validated structured output
    citations: dict                # claims, confidence, dropped_source_ids, invalid_inline
    answer: str


# ── LLM factory ──────────────────────────────────────────────────────────────

def _agent_llm():
    """Structured-output model for the router, grader and groundedness checker (monkeypatched in tests)."""
    settings = get_settings()
    return gemini_structured_llm(settings.AGENT_MODEL, settings.GOOGLE_API_KEY, settings.AGENT_MAX_TOKENS)


def _build_llm(settings) -> ChatGoogleGenerativeAI:
    """Return a streaming-capable Gemini chat model."""
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.1,          # low temperature for factual RAG
        streaming=True,           # enables on_chat_model_stream events
        convert_system_message_to_human=False,
    )


# ── Graph nodes ───────────────────────────────────────────────────────────────

async def _router_node(state: RAGState) -> dict:
    """
    Decide whether this turn needs a document lookup at all.

    With the agentic loop off this is a passthrough (no LLM call): every turn retrieves, as before.
    """
    if not get_settings().ENABLE_AGENTIC_LOOP:
        return {"route": "needs_retrieval"}
    route = await classify_turn(state["query"], state["history_messages"], _agent_llm())
    logger.info("router_node: route=%s query=%r", route, state["query"][:80])
    return {"route": route}


async def _rewrite_retry_node(state: RAGState, settings) -> dict:
    """A retry: the previous search retrieved weakly, so ask for a differently-phrased or broader query."""
    query = state["query"]
    llm = gemini_rewrite_llm(
        settings.QUERY_REWRITE_MODEL, settings.GOOGLE_API_KEY, settings.QUERY_REWRITE_MAX_TOKENS
    )
    try:
        raw = await llm(build_retry_prompt(query, state["history_messages"], state["failed_queries"]))
        candidate = guard_rewrite(query, raw)
        candidate = candidate and keep_identifiers(query, candidate)
    except Exception as exc:
        logger.warning("Retry rewrite failed, reusing the previous query: %s", exc)
        candidate = None
    search_query = candidate or state["search_query"]
    logger.info(
        "rewrite_retry: attempt=%d %r -> %r", state["retrieval_attempt"], state["search_query"][:60], search_query[:60]
    )
    return {"search_query": search_query, "rewrite_applied": search_query != query}


async def _rewrite_query_node(state: RAGState) -> dict:
    """
    Turn a follow-up into a standalone search query before retrieval.

    With no history (or the flag off) this is a pure passthrough: no LLM call, no added latency.
    On a retry (agentic loop) it asks for a differently-phrased or broader query instead.
    """
    settings = get_settings()
    query = state["query"]
    if state["retrieval_attempt"] > 0:
        return await _rewrite_retry_node(state, settings)
    if not settings.ENABLE_QUERY_REWRITE or not state["history_messages"]:
        return {"search_query": query, "rewrite_applied": False}

    llm = gemini_rewrite_llm(
        settings.QUERY_REWRITE_MODEL, settings.GOOGLE_API_KEY, settings.QUERY_REWRITE_MAX_TOKENS
    )
    search_query, applied = await rewrite_query(
        query, state["history_messages"], llm, settings.QUERY_REWRITE_HISTORY_TURNS
    )
    logger.info("rewrite_query_node: original=%r rewritten=%r applied=%s", query[:80], search_query[:80], applied)
    return {"search_query": search_query, "rewrite_applied": applied}


def _source_dict(c: RetrievedChunk) -> dict:
    return {
        "document_id": c.document_id,
        "filename": c.filename,
        "page_number": c.page_number,
        "chunk_index": c.chunk_index,
        "text_snippet": c.text[:300],
        "score": round(c.score, 4),
        "chunk_id": c.chunk_id,
        "rerank_score": None if c.rerank_score is None else round(c.rerank_score, 4),
        "heading": c.heading,
        "section": c.section,
    }


async def _retrieve_node(state: RAGState) -> dict:
    """
    Embed the standalone search query and fetch the top-k chunks from Qdrant.

    Produces:
        chunks  — list[RetrievedChunk] for the generate node
        sources — serialisable list[dict] emitted in the SSE sources event
    """
    chunks = await retrieve_chunks(query=state["search_query"], top_k=state["top_k"])

    sources = [_source_dict(c) for c in chunks]

    logger.info(
        "retrieve_node: %d chunks for query=%r",
        len(chunks),
        state["query"][:80],
    )
    return {
        "chunks": chunks,
        "sources": sources,
        "timings_ms": get_stage_timings(),
        "retrieval_attempt": state["retrieval_attempt"] + 1,
    }


async def _grade_chunks_node(state: RAGState) -> dict:
    """
    Grade the retrieved chunks. Weak retrieval loops back to a rewritten query (capped by
    MAX_RETRIEVAL_LOOPS); otherwise only relevant/partial chunks go on to generation.
    """
    settings = get_settings()
    chunks = state["chunks"]
    grades = await grade_chunks(state["search_query"], [c.text for c in chunks], _agent_llm())
    weak = is_weak(grades, settings.MIN_RELEVANT_CHUNKS)
    logger.info("grade_chunks_node: grades=%s weak=%s attempt=%d", grades, weak, state["retrieval_attempt"])
    pool = [*state["pool"], *zip(chunks, grades)]
    if weak and should_retry(True, state["retrieval_attempt"], settings.MAX_RETRIEVAL_LOOPS):
        return {"chunk_grades": grades, "retrieval_weak": True, "pool": pool,
                "failed_queries": [*state["failed_queries"], state["search_query"]]}
    # The final context is chosen across all attempts, so a good first hit survives a drifting retry.
    by_id = {c.chunk_id: c for c, _ in pool}
    chosen = [by_id[cid] for cid in select_from_pool([(c.chunk_id, g) for c, g in pool], state["top_k"])]
    return {"chunk_grades": grades, "retrieval_weak": weak, "pool": pool,
            "chunks": chosen, "sources": [_source_dict(c) for c in chosen]}


_DIRECT_SYSTEM = (
    "You are a friendly assistant for a private document knowledge base. Reply briefly. Greet back, thank the "
    "user, or say goodbye when they do. If asked what you can do, say you answer questions about the documents "
    "they have uploaded. If asked to repeat or rephrase your previous message, do so using the conversation. "
    "If the message is too vague to search for, ask ONE short clarifying question. Never state facts about the "
    "documents' contents."
)


async def _direct_response_node(state: RAGState) -> dict:
    """Answer chitchat / clarification turns without any retrieval. Streams like the generate node."""
    llm = _build_llm(get_settings())
    messages: list[BaseMessage] = [
        SystemMessage(content=_DIRECT_SYSTEM), *state["history_messages"][-6:], HumanMessage(content=state["query"])
    ]
    response = await llm.ainvoke(messages)
    answer = response.content if isinstance(response.content, str) else str(response.content)
    return {"answer": answer, "chunks": [], "sources": []}


async def _check_grounded_node(state: RAGState) -> dict:
    """Verify the finished answer against the chunks it was generated from; append a caveat if unsupported."""
    settings = get_settings()
    if not settings.ENABLE_GROUNDEDNESS_CHECK or not state["chunks"] or not state["answer"].strip():
        return {}
    verdict = await check_groundedness(state["answer"], [c.text for c in state["chunks"]], _agent_llm())
    if verdict is None:
        return {"groundedness": {"grounded": None, "unsupported_claims": []}}
    result = {"grounded": verdict.grounded, "unsupported_claims": verdict.unsupported_claims}
    if verdict.grounded:
        return {"groundedness": result}
    return {"groundedness": result, "answer": state["answer"] + UNGROUNDED_CAVEAT}


async def _generate_node(state: RAGState) -> dict:
    """
    Build the RAG prompt and call the LLM.

    Because the LLM has ``streaming=True``, LangGraph's event bus emits
    ``on_chat_model_stream`` events for every token while this node awaits
    the ``ainvoke`` call.  The API layer captures those events.

    Produces:
        answer — the complete assistant response text
    """
    settings = get_settings()
    llm = _build_llm(settings)

    # Build context block from retrieved chunks
    if state["chunks"]:
        context_parts: list[str] = []
        for i, chunk in enumerate(state["chunks"], start=1):
            where = chunk.filename
            if settings.INCLUDE_CHUNK_METADATA_IN_PROMPT:
                where = " › ".join(p for p in (chunk.filename, chunk.section, chunk.heading) if p)
            header = f"[Source {i}] {where}, page {chunk.page_number} (relevance: {chunk.score:.2f})"
            context_parts.append(f"{header}\n{chunk.text}")
        context = "\n\n---\n\n".join(context_parts)
    else:
        context = (
            "No relevant documents were found in the knowledge base for this query."
        )

    # Trim prior AIMessage content to reduce the model's surface area for
    # repetition.  Long prior answers are the main trigger for repetition;
    # 400 chars preserves coreference ability without inviting copy-paste.
    trimmed_history: list[BaseMessage] = []
    for msg in state["history_messages"]:
        if isinstance(msg, AIMessage) and isinstance(msg.content, str) and len(msg.content) > 400:
            trimmed_history.append(AIMessage(content=msg.content[:400] + " …[truncated]"))
        else:
            trimmed_history.append(msg)

    # Assemble message list:
    #   system prompt (with context) → trimmed history → current query
    #
    # The instruction reminder is embedded directly in the user turn because
    # Gemini rejects consecutive SystemMessages (returns empty output).
    # Prefixing the question with an explicit instruction is the safest,
    # most compatible way to enforce focus at generation time.
    focused_query = (
        f"[INSTRUCTION: Answer ONLY the following question. "
        f"Do NOT repeat or preface with content from previous turns.]\n\n"
        f"{state['query']}"
    )
    structured = bool(settings.ENABLE_VERIFIED_CITATIONS and state["chunks"])
    system_prompt = _SYSTEM_TEMPLATE.format(context=context) + (STRUCTURED_OUTPUT_INSTRUCTIONS if structured else "")
    messages: list[BaseMessage] = [
        SystemMessage(content=system_prompt),
        *trimmed_history,
        HumanMessage(content=focused_query),
    ]

    logger.debug(
        "generate_node: invoking LLM with %d messages (%d history)",
        len(messages),
        len(state["history_messages"]),
    )

    response = await llm.ainvoke(messages)
    answer: str = response.content if isinstance(response.content, str) else str(response.content)

    if not structured:
        return {"answer": answer, "structured": False}

    parsed = parse_structured_answer(answer)
    if parsed is None:
        logger.warning("Structured output was not valid JSON; using the raw text with no verified claims")
        return {"answer": answer, "structured": False}

    claims, dropped = validate_claims(parsed.claims, len(state["chunks"]))
    invalid_inline = find_invalid_inline_citations(
        parsed.answer, [(c.filename, c.page_number) for c in state["chunks"]]
    )
    if dropped or invalid_inline:
        logger.warning("Citation check: dropped %d invented source ids, %d invalid inline citations",
                       dropped, len(invalid_inline))
    return {
        "answer": parsed.answer,
        "structured": True,
        "citations": {
            "claims": [c.model_dump() for c in claims],
            "confidence": parsed.confidence,
            "dropped_source_ids": dropped,
            "invalid_inline": [{"filename": f, "page": p} for f, p in invalid_inline],
        },
    }


async def _save_history_node(state: RAGState) -> dict:
    """
    Persist the current user+assistant turn to PostgreSQL.

    This node runs after streaming completes, so the full answer is available.
    """
    await save_turn(
        conversation_id=uuid.UUID(state["conversation_id"]),
        user_message=state["query"],
        assistant_message=state["answer"],
    )
    logger.debug("save_history_node: turn saved for conv=%s", state["conversation_id"])
    return {}


# ── Graph compilation ─────────────────────────────────────────────────────────

def _after_router(state: RAGState) -> str:
    return "rewrite_query" if state["route"] == "needs_retrieval" else "direct_response"


def _after_retrieve(state: RAGState) -> str:
    return "grade_chunks" if get_settings().ENABLE_AGENTIC_LOOP else "generate"


def _after_grade(state: RAGState) -> str:
    """Retry through a rewritten query while retrieval is weak and the loop cap allows it; otherwise generate."""
    retry = should_retry(state["retrieval_weak"], state["retrieval_attempt"], get_settings().MAX_RETRIEVAL_LOOPS)
    return "rewrite_query" if retry else "generate"


def _compile_graph():
    graph: StateGraph = StateGraph(RAGState)

    graph.add_node("router", _router_node)
    graph.add_node("rewrite_query", _rewrite_query_node)
    graph.add_node("retrieve", _retrieve_node)
    graph.add_node("grade_chunks", _grade_chunks_node)
    graph.add_node("generate", _generate_node)
    graph.add_node("direct_response", _direct_response_node)
    graph.add_node("check_grounded", _check_grounded_node)
    graph.add_node("save_history", _save_history_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", _after_router, ["rewrite_query", "direct_response"])
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_conditional_edges("retrieve", _after_retrieve, ["grade_chunks", "generate"])
    graph.add_conditional_edges("grade_chunks", _after_grade, ["rewrite_query", "generate"])
    graph.add_edge("generate", "check_grounded")
    graph.add_edge("check_grounded", "save_history")
    graph.add_edge("direct_response", "save_history")
    graph.add_edge("save_history", END)

    return graph.compile()


# Lazy-init singleton — the compiled graph is stateless and safe to share.
_rag_graph = None


def get_rag_graph():
    global _rag_graph
    if _rag_graph is None:
        _rag_graph = _compile_graph()
        logger.info("LangGraph RAG graph compiled and cached")
    return _rag_graph


# ── Public streaming interface ────────────────────────────────────────────────

async def stream_rag(
    query: str,
    conversation_id: str,
    history_messages: list[BaseMessage],
    top_k: int,
) -> AsyncGenerator[dict, None]:
    """
    Execute the RAG graph and yield typed event dicts for the SSE layer.

    Yielded event shapes:
        {"type": "sources",  "sources": [...], "retrieved_count": N}
        {"type": "chunk",    "content": "<token>"}
        {"type": "done",     "conversation_id": "<uuid>", "total_chars": N}

    The caller is responsible for wrapping each dict as an SSE ``data:`` line.

    Args:
        query:             User's question.
        conversation_id:   String UUID of the active conversation.
        history_messages:  Previous turns as LangChain messages.
        top_k:             Chunks to retrieve.
    """
    graph = get_rag_graph()

    initial_state: RAGState = {
        "query": query,
        "search_query": query,
        "rewrite_applied": False,
        "conversation_id": conversation_id,
        "history_messages": history_messages,
        "top_k": top_k,
        "chunks": [],
        "sources": [],
        "timings_ms": {},
        "route": "needs_retrieval",
        "retrieval_attempt": 0,
        "retrieval_weak": False,
        "chunk_grades": [],
        "failed_queries": [],
        "pool": [],
        "groundedness": {},
        "structured": False,
        "citations": {},
        "answer": "",
    }

    settings = get_settings()
    verified = settings.ENABLE_VERIFIED_CITATIONS
    extractor = AnswerStreamExtractor()
    total_chars = 0
    started, route, outcome, attempts = time.perf_counter(), "needs_retrieval", "ok", 0
    answer, grounded = "", None
    trace = tracing.start_trace(query, conversation_id)

    try:
        async for event in graph.astream_events(
            initial_state, version="v2", config={"callbacks": tracing.langchain_callbacks(trace)}
        ):
            kind: str = event["event"]
            name: str = event.get("name", "")

            # ── After router: report a non-retrieval route ─────────────────────
            if kind == "on_chain_end" and name == "router":
                route = event["data"].get("output", {}).get("route", "needs_retrieval")
                if route != "needs_retrieval":
                    yield {"type": "route", "route": route}

            # ── After rewrite node: tell the client what was actually searched ──
            elif kind == "on_chain_end" and name == "rewrite_query":
                output = event["data"].get("output", {})
                if output.get("rewrite_applied"):
                    yield {"type": "query_rewrite", "original": query, "rewritten": output["search_query"]}

            # ── After retrieve node: emit sources (again on every retry) ────────
            elif kind == "on_chain_end" and name == "retrieve":
                output = event["data"].get("output", {})
                attempts = output.get("retrieval_attempt", attempts)
                for stage, ms in (output.get("timings_ms") or {}).items():
                    metrics.STAGE_SECONDS.labels(stage.removesuffix("_ms")).observe(ms / 1000)
                sources: list[dict] = output.get("sources", [])
                yield {
                    "type": "sources",
                    "sources": sources,
                    "retrieved_count": len(sources),
                    "timings_ms": output.get("timings_ms", {}),
                }

            # ── After grading: per-chunk grades and whether a retry follows ─────
            elif kind == "on_chain_end" and name == "grade_chunks":
                output = event["data"].get("output", {})
                yield {"type": "chunk_grades", "grades": output.get("chunk_grades", []),
                       "weak": output.get("retrieval_weak", False)}
                if "sources" in output:  # the final context: [Source N] in the answer refers to this list
                    yield {"type": "sources", "sources": output["sources"], "retrieved_count": len(output["sources"]),
                           "timings_ms": {}}

            # ── After the groundedness check: verdict, plus a visible caveat if unsupported ──
            elif kind == "on_chain_end" and name == "check_grounded":
                verdict = event["data"].get("output", {}).get("groundedness")
                grounded = verdict.get("grounded") if verdict else None
                if verdict:
                    yield {"type": "groundedness", **verdict}
                    if verdict.get("grounded") is False:
                        outcome = "ungrounded"
                        total_chars += len(UNGROUNDED_CAVEAT)
                        yield {"type": "chunk", "content": UNGROUNDED_CAVEAT}

            # ── Final answer text (for the trace) ───────────────────────────────
            elif kind == "on_chain_end" and (name == "direct_response" or (name == "generate" and not verified)):
                answer = event["data"].get("output", {}).get("answer", "") or answer

            # ── Token usage of the LangChain calls (generate / direct_response) ──
            elif kind == "on_chat_model_end":
                usage = getattr(event["data"].get("output"), "usage_metadata", None) or {}
                metrics.record_llm_usage(
                    settings.GEMINI_MODEL, event.get("metadata", {}).get("langgraph_node", "llm"),
                    usage.get("input_tokens", 0), usage.get("output_tokens", 0),
                )

            # ── LLM token streaming (answer tokens only, never helper models) ───
            elif kind == "on_chat_model_stream" and event.get("metadata", {}).get("langgraph_node") in (
                "generate",
                "direct_response",
            ):
                chunk = event["data"].get("chunk")
                if chunk is None:
                    continue

                # AIMessageChunk.content can be str or list[dict] (multimodal)
                raw = chunk.content if hasattr(chunk, "content") else ""
                if isinstance(raw, list):
                    token = "".join(
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in raw
                    )
                else:
                    token = str(raw)

                # Structured mode: the model emits JSON, so stream only the decoded "answer" text.
                if verified and event["metadata"]["langgraph_node"] == "generate":
                    token = extractor.feed(token)
                if token:
                    total_chars += len(token)
                    yield {"type": "chunk", "content": token}

            # ── Generation finished: validated citations, and a fallback if nothing streamed ──
            elif kind == "on_chain_end" and name == "generate" and verified:
                output = event["data"].get("output", {})
                answer = output.get("answer", "") or answer
                if not extractor.started and output.get("answer"):
                    total_chars += len(output["answer"])          # plain-text answer: emit it in one piece
                    yield {"type": "chunk", "content": output["answer"]}
                if output.get("structured"):
                    yield {"type": "citations", **output["citations"]}

        # ── Graph complete ─────────────────────────────────────────────────────────
        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "total_chars": total_chars,
        }
    except Exception as e:
        outcome = "error"
        logger.error(f"Error during RAG generation: {e}")
        yield {
            "type": "error",
            "message": f"Generation failed: {str(e)}"
        }
    finally:
        tracing.end_trace(trace, answer, {
            "route": route, "outcome": outcome, "retrieval_attempts": attempts, "grounded": grounded,
            "latency_s": round(time.perf_counter() - started, 3),
        })
        metrics.QUERIES.labels(route, outcome).inc()
        metrics.QUERY_SECONDS.labels(route).observe(time.perf_counter() - started)
        if attempts:
            metrics.RETRIEVAL_ATTEMPTS.observe(attempts)
