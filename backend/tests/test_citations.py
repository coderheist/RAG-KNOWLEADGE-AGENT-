"""Unit tests for verified citations (Phase 4): streaming extraction, parsing, and source-id validation."""
import json

import pytest

from app.services.citations import (
    AnswerStreamExtractor,
    Claim,
    find_invalid_inline_citations,
    parse_structured_answer,
    validate_claims,
)

ANSWER = 'The limit is "600" req/min (spec.md, p. 1).\nSee C:\\docs\\file — café ☕.'
PAYLOAD = json.dumps(
    {"answer": ANSWER, "claims": [{"text": "limit is 600", "source_ids": [1]}], "confidence": "high"},
    ensure_ascii=False,
)
PAYLOAD_ASCII = json.dumps({"answer": ANSWER, "claims": [], "confidence": "low"})       # \u escapes


@pytest.mark.parametrize("payload", [PAYLOAD, PAYLOAD_ASCII, "```json\n" + PAYLOAD + "\n```"])
@pytest.mark.parametrize("size", [1, 2, 3, 5, 7, 11, 64])
def test_extractor_reproduces_the_answer_at_every_chunk_size(payload: str, size: int) -> None:
    extractor = AnswerStreamExtractor()
    streamed = "".join(extractor.feed(payload[i : i + size]) for i in range(0, len(payload), size))
    assert streamed == ANSWER
    assert extractor.started and extractor.finished


def test_extractor_streams_incrementally_before_the_json_is_complete() -> None:
    extractor = AnswerStreamExtractor()
    assert extractor.feed('{"ans') == ""
    assert extractor.feed('wer": "Hel') == "Hel"
    assert extractor.feed('lo wor') == "lo wor"
    assert extractor.feed('ld", "claims": []}') == "ld"


def test_extractor_holds_back_a_split_escape_sequence() -> None:
    extractor = AnswerStreamExtractor()
    assert extractor.feed('{"answer": "a\\') == "a"          # backslash at the end of the chunk
    assert extractor.feed('nb"}') == "\nb"


def test_extractor_reports_not_started_for_plain_text() -> None:
    extractor = AnswerStreamExtractor()
    assert extractor.feed("The rate limit is 600 requests per minute.") == ""
    assert extractor.started is False


def test_parse_structured_answer() -> None:
    parsed = parse_structured_answer(PAYLOAD)
    assert parsed is not None and parsed.answer == ANSWER and parsed.confidence == "high"
    assert parse_structured_answer("```json\n" + PAYLOAD + "\n```") is not None
    assert parse_structured_answer("just some plain text") is None
    assert parse_structured_answer('{"claims": []}') is None                  # missing the required answer


def test_validate_claims_drops_invented_source_ids() -> None:
    claims = [
        Claim(text="a", source_ids=[1, 9]),
        Claim(text="b", source_ids=[3, 3, 2]),
        Claim(text="c", source_ids=[0]),
    ]
    cleaned, dropped = validate_claims(claims, n_sources=3)
    assert [c.source_ids for c in cleaned] == [[1], [2, 3], []]
    assert dropped == 2                                                       # 9 and 0; a duplicate 3 is not "invented"


def test_find_invalid_inline_citations() -> None:
    answer = "Rate is 600 (spec.md, p. 1). Also 9 (ghost.pdf, p. 4). Again (spec.md, p. 2)."
    assert find_invalid_inline_citations(answer, [("spec.md", 1)]) == [("ghost.pdf", 4), ("spec.md", 2)]
    assert find_invalid_inline_citations("no citations here", [("spec.md", 1)]) == []
