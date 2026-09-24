"""Upload the fixture PDF to POST /upload and verify the ingestion pipeline result."""
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.integration

PDF_PATH = Path(__file__).parent / "fixtures" / "test.pdf"
URL = "http://localhost:8000/upload"


def test_upload_pdf_runs_full_pipeline() -> None:
    with httpx.Client(timeout=120) as client, PDF_PATH.open("rb") as f:
        resp = client.post(URL, files={"files": ("test_upload.pdf", f, "application/pdf")})

    assert resp.status_code == 200, resp.text
    doc = resp.json()["documents"][0]

    assert doc["status"] in ("completed", "already_exists"), f"unexpected status {doc['status']!r}: {doc.get('error')}"
    assert doc["chunk_count"] > 0, f"chunk_count is {doc['chunk_count']}"
    assert doc["page_count"] > 0, f"page_count is {doc['page_count']}"
