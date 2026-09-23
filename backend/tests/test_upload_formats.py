"""Upload every supported document format and assert each indexes cleanly.

Requires a live API + Postgres + Qdrant (docker compose up), hence marked
integration. Fixtures are generated in-memory so the test is self-contained
and doesn't depend on /tmp state (replaces the old test_all.py / test_all_formats.py
manual scripts).
"""
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.integration

API_URL = "http://localhost:8000"
FORMATS = ["pdf", "docx", "pptx", "xlsx", "csv", "txt", "md"]


def _make_fixture(path: Path, ext: str) -> None:
    if ext == "txt":
        path.write_text("This is a simple text file for testing TXT parsing.")
    elif ext == "md":
        path.write_text("# Markdown Test\n\nThis is a markdown file with a **bold** word.")
    elif ext == "csv":
        path.write_text("Name,Age\nAlice,25\nBob,30\n")
    elif ext == "docx":
        from docx import Document

        doc = Document()
        doc.add_paragraph("This is a Word document for testing DOCX parsing.")
        doc.save(path)
    elif ext == "pptx":
        from pptx import Presentation

        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = "PPTX Test"
        slide.placeholders[1].text = "This is a PowerPoint presentation."
        prs.save(path)
    elif ext == "xlsx":
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["Item", "Cost"])
        ws.append(["Apple", 1.2])
        wb.save(path)
    elif ext == "pdf":
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "This is a standard PDF file for testing PDF parsing.")
        doc.save(path)
        doc.close()
    else:
        raise ValueError(f"no fixture generator for {ext}")


@pytest.fixture
def format_fixtures(tmp_path: Path) -> dict[str, Path]:
    paths = {}
    for ext in FORMATS:
        p = tmp_path / f"test.{ext}"
        _make_fixture(p, ext)
        paths[ext] = p
    return paths


@pytest.mark.parametrize("ext", FORMATS)
def test_upload_indexes_each_format(format_fixtures: dict[str, Path], ext: str) -> None:
    path = format_fixtures[ext]
    with httpx.Client(timeout=60) as client, path.open("rb") as f:
        resp = client.post(f"{API_URL}/upload", files={"files": (path.name, f, "application/octet-stream")})

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["documents"], f"no documents returned for {ext}"
    doc = data["documents"][0]
    assert doc["status"] in ("completed", "already_exists"), f"{ext} upload failed: {doc}"
