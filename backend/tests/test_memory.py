"""Conversation memory: a follow-up question must be answered using the
conversation_id from the prior turn, not in isolation (replaces test_memory.py script).
"""
import json

import httpx
import pytest

pytestmark = pytest.mark.integration

API_BASE = "http://localhost:8000"


async def _stream_query(client: httpx.AsyncClient, **payload) -> dict:
    resp = await client.post(f"{API_BASE}/query", json=payload)
    answer = ""
    conversation_id = None
    async for line in resp.aiter_lines():
        if not line or "data: " not in line:
            continue
        payload = line.replace("data: ", "", 1)
        if payload == "[DONE]":
            break
        data = json.loads(payload)
        if data.get("type") == "chunk":
            answer += data.get("content", "")
        elif data.get("type") == "done":
            conversation_id = data.get("conversation_id")
    return {"answer": answer, "conversation_id": conversation_id}


async def test_followup_question_uses_conversation_history() -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        first = await _stream_query(
            client, query="My name is Sachin. I'm testing memory.", top_k=2
        )
        assert first["conversation_id"], "first turn did not return a conversation_id"

        second = await _stream_query(
            client,
            query="What is my name?",
            conversation_id=first["conversation_id"],
            top_k=2,
        )

    assert "sachin" in second["answer"].lower(), (
        f"expected the follow-up answer to recall the name from turn 1, got: {second['answer']!r}"
    )
