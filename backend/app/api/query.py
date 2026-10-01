"""
RAG query API router (Phase 4).

POST /query — accepts a JSON body, runs the LangGraph RAG pipeline,
              and streams the response as Server-Sent Events (SSE).

SSE event stream format
────────────────────────
Every event is a JSON object on a ``data:`` line, terminated by
two newlines (per the SSE spec).

    data: {"type":"thinking"}

    data: {"type":"sources","sources":[...],"retrieved_count":5}

    data: {"type":"chunk","content":"The annual report..."}

    data: {"type":"chunk","content":" shows revenue growth..."}

    data: {"type":"done","conversation_id":"<uuid>","total_chars":412}

    data: [DONE]

Error event (only when the pipeline fails mid-stream):

    data: {"type":"error","message":"<description>"}

    data: [DONE]

Client-side usage example (JavaScript):

    const es = new EventSource(undefined);
    const resp = await fetch("/query", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({query: "...", conversation_id: null}),
    });
    const reader = resp.body.getReader();
    // read SSE lines and parse JSON from each `data:` line
"""

import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.schemas.query import HistoryTurn, QueryRequest, SSEThinking
from app.services.conversation_service import get_or_create_conversation, load_history
from app.services.library_service import collection_exists
from app.services.rag_graph import stream_rag
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Query"])

# SSE helpers ──────────────────────────────────────────────────────────────────

def _sse(payload: dict | str) -> str:
    """Format a single SSE data line."""
    if isinstance(payload, str):
        return f"data: {payload}\n\n"
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# Streaming generator ──────────────────────────────────────────────────────────

def _client_history(turns: list[HistoryTurn]) -> list[BaseMessage]:
    return [HumanMessage(content=t.content) if t.role == "user" else AIMessage(content=t.content) for t in turns]


async def _generate_sse(
    request: Request,
    query: str,
    conversation_id: uuid.UUID | None,
    top_k: int,
    client_history: list[HistoryTurn] | None = None,
    collection_id: uuid.UUID | None = None,
) -> AsyncGenerator[str, None]:
    """
    Async generator that drives the entire RAG pipeline and yields raw SSE
    strings suitable for a StreamingResponse.

    Pipeline:
        1. Resolve / create conversation (PostgreSQL)
        2. Load conversation history (PostgreSQL)
        3. Yield "thinking" event immediately
        4. Run LangGraph astream_events:
             a. After retrieve node  → yield "sources" event
             b. Per LLM token        → yield "chunk" event
             c. After graph end      → yield "done" event
        5. Yield "[DONE]" SSE terminator
    """
    # ── 1+2. Conversation setup ───────────────────────────────────────────────
    try:
        conv_id = await get_or_create_conversation(conversation_id)
        if conversation_id is None and client_history:
            history = _client_history(client_history)
        else:
            history = await load_history(conv_id)
    except Exception as exc:
        logger.exception("Conversation setup failed: %s", exc)
        yield _sse({"type": "error", "message": f"Conversation setup failed: {exc}"})
        yield _sse("[DONE]")
        return

    # ── 3. Immediate "thinking" event ─────────────────────────────────────────
    yield _sse(SSEThinking().model_dump())

    # ── 4. LangGraph streaming ────────────────────────────────────────────────
    try:
        async for graph_event in stream_rag(
            query=query,
            conversation_id=str(conv_id),
            history_messages=history,
            top_k=top_k,
            collection_id=str(collection_id) if collection_id else None,
        ):
            # Check for client disconnect on each event to stop early
            if await request.is_disconnected():
                logger.info("Client disconnected mid-stream for conv=%s", conv_id)
                return

            yield _sse(graph_event)

    except Exception as exc:
        logger.exception("RAG graph stream error for conv=%s: %s", conv_id, exc)
        yield _sse({"type": "error", "message": str(exc)})

    # ── 5. SSE stream terminator ──────────────────────────────────────────────
    yield _sse("[DONE]")


# Router endpoint ──────────────────────────────────────────────────────────────

@router.post(
    "/query",
    summary="RAG query with streaming response",
    description=(
        "Submit a natural-language question. The response is a "
        "**Server-Sent Events** stream.\n\n"
        "Set `Accept: text/event-stream` or simply consume the stream — "
        "FastAPI will set `Content-Type: text/event-stream` automatically.\n\n"
        "**Event types** (in order):\n"
        "- `thinking` — pipeline started\n"
        "- `sources`  — retrieved document chunks (before any tokens)\n"
        "- `chunk`    — one LLM token or small token batch\n"
        "- `done`     — answer complete; includes `conversation_id` for follow-up\n"
        "- `error`    — unrecoverable failure (stream still closes cleanly)\n\n"
        "Pass the returned `conversation_id` in subsequent requests to continue "
        "the conversation with full memory."
    ),
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE stream of RAG events",
            "content": {"text/event-stream": {}},
        },
        422: {"description": "Validation error — invalid request body"},
    },
)
async def query_endpoint(
    body: QueryRequest,
    request: Request,
) -> StreamingResponse:
    if body.collection_id is not None and not await collection_exists(body.collection_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found.")

    logger.info(
        "POST /query | conv=%s top_k=%d query=%r",
        body.conversation_id,
        body.top_k,
        body.query[:80],
    )

    return StreamingResponse(
        _generate_sse(
            request=request,
            query=body.query,
            conversation_id=body.conversation_id,
            top_k=body.top_k,
            client_history=body.history,
            collection_id=body.collection_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",       # disable nginx proxy buffering
            "Access-Control-Allow-Origin": "*",
        },
    )
