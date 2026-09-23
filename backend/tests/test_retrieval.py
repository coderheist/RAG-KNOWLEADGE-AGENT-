"""Retrieval smoke tests: a query against indexed fixtures must stream a
non-empty answer with at least one cited source (replaces test_retrieval.py
and test_retrieval_2.py — same target, kept as one file instead of a "_2" copy).
"""
import json

import httpx
import pytest

pytestmark = pytest.mark.integration

API_URL = "http://localhost:8000"

QUERIES = [
    "What is the cost of Apple?",
    "How old is Alice?",
    "What kind of file is this markdown file?",
]


async def _stream_query(client: httpx.AsyncClient, query: str) -> dict:
    resp = await client.post(f"{API_URL}/query", json={"query": query, "top_k": 5})
    answer = ""
    sources: list = []
    async for line in resp.aiter_lines():
        if not line or "data: " not in line:
            continue
        payload = line.replace("data: ", "", 1)
        if payload == "[DONE]":
            break
        data = json.loads(payload)
        if data.get("type") == "chunk":
            answer += data.get("content", "")
        elif data.get("type") == "sources":
            sources = data.get("sources", [])
    return {"answer": answer, "sources": sources}


@pytest.mark.parametrize("query", QUERIES)
async def test_query_streams_answer_with_sources(query: str) -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        result = await _stream_query(client, query)

    assert result["answer"].strip(), f"empty answer for query: {query!r}"
    assert result["sources"], f"no cited sources for query: {query!r}"
