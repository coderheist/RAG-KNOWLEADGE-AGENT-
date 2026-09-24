"""Deterministic checks for evals.metrics.generation (the LLM judge is stubbed)."""
import pytest

from evals.metrics import generation
from evals.metrics.generation import citation_accuracy, extract_citations, refusal_correctness

CHUNKS = [
    {"filename": "spec.md", "page_number": 1, "text": "The rate limit is 600 requests per minute."},
    {"filename": "pricing.xlsx", "page_number": 1, "text": "HW-ND-2201 costs 184.50."},
]


def test_extract_citations_finds_file_page_and_claim() -> None:
    answer = "The limit is 600 requests per minute (spec.md, p. 1). The SKU costs 184.50 (pricing.xlsx, p. 1)."
    cites = extract_citations(answer)
    assert [(f, p) for f, p, _ in cites] == [("spec.md", 1), ("pricing.xlsx", 1)]
    assert "600 requests per minute" in cites[0][2]


def test_extract_citations_ignores_non_citations() -> None:
    assert extract_citations("Hello there (just a note).") == []


@pytest.mark.parametrize(
    ("category", "refused", "expected"),
    [("unanswerable", True, 1.0), ("unanswerable", False, 0.0), ("factual_lookup", False, 1.0),
     ("factual_lookup", True, 0.0), ("chitchat", False, 1.0)],
)
def test_refusal_correctness(category: str, refused: bool, expected: float) -> None:
    assert refusal_correctness(category, refused).score == expected


async def test_citation_accuracy_none_for_refusal_and_zero_without_citations() -> None:
    assert (await citation_accuracy("I don't know.", CHUNKS, refused=True)).score is None
    assert (await citation_accuracy("It is 600 per minute.", CHUNKS, refused=False)).score == 0.0


async def test_citation_accuracy_counts_unretrieved_sources_as_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_judge(prompt: str, model: str) -> dict:
        return {"verdicts": [{"id": 1, "supported": True}]}

    monkeypatch.setattr(generation, "_judge_json", fake_judge)
    answer = "The limit is 600 requests per minute (spec.md, p. 1). It is also 9 (ghost.pdf, p. 4)."
    result = await citation_accuracy(answer, CHUNKS, refused=False)
    assert result.score == 0.5
    assert "1 cite a source that was not retrieved" in result.reason
