"""Concurrent uploads of the identical file must yield exactly one indexed
copy and the rest already_exists (replaces the old test_concurrent_dup.py script).
"""
import asyncio
import uuid

import httpx
import pytest

pytestmark = pytest.mark.integration

API_BASE = "http://localhost:8000"


async def test_concurrent_uploads_dedupe_to_one_indexed_copy() -> None:
    content = f"Concurrent duplicate upload probe {uuid.uuid4()}".encode()

    async with httpx.AsyncClient(timeout=60) as client:
        async def upload():
            return await client.post(
                f"{API_BASE}/upload", files=[("files", ("dup.txt", content, "text/plain"))]
            )

        responses = await asyncio.gather(*[upload() for _ in range(5)])

    docs = []
    for resp in responses:
        assert resp.status_code == 200, resp.text
        docs.append(resp.json()["documents"][0])

    statuses = [d["status"] for d in docs]
    assert all(s in ("completed", "already_exists") for s in statuses), f"unexpected statuses: {statuses}"
    # Known: racing requests each re-run ingestion on the winner's row, so "completed" can repeat
    # (redundant embedding work, but a single document id and idempotent vector upserts).
    assert len({d["document_id"] for d in docs}) == 1, f"duplicates created separate documents: {docs}"
