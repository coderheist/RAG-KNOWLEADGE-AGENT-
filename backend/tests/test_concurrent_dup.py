"""Concurrent uploads of the identical file must yield exactly one indexed
copy and the rest already_exists (replaces the old test_concurrent_dup.py script).
"""
import asyncio

import httpx
import pytest

pytestmark = pytest.mark.integration

API_BASE = "http://localhost:8000"


async def test_concurrent_uploads_dedupe_to_one_indexed_copy() -> None:
    content = b"Exact same file content across 5 concurrent uploads."

    async with httpx.AsyncClient(timeout=60) as client:
        async def upload():
            return await client.post(
                f"{API_BASE}/upload", files=[("files", ("dup.txt", content, "text/plain"))]
            )

        responses = await asyncio.gather(*[upload() for _ in range(5)])

    statuses = []
    for resp in responses:
        assert resp.status_code == 200, resp.text
        doc = resp.json()["documents"][0]
        statuses.append(doc["status"])

    assert statuses.count("completed") == 1, f"expected exactly one indexed upload, got {statuses}"
    assert statuses.count("already_exists") == 4, f"expected 4 duplicates flagged, got {statuses}"
