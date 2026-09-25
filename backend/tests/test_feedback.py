"""Unit tests for the feedback loop (Phase 6): request validation and thumbs-down -> eval candidate."""
import pytest
from pydantic import ValidationError

from app.schemas.feedback import FeedbackRequest
from scripts.feedback_to_eval import to_candidate


def test_feedback_request_validation() -> None:
    ok = FeedbackRequest(rating="down", question="q", answer="a", chunk_ids=["c1"], comment="wrong number")
    assert ok.rating == "down" and ok.conversation_id is None
    with pytest.raises(ValidationError):
        FeedbackRequest(rating="meh", question="q", answer="a")
    with pytest.raises(ValidationError):
        FeedbackRequest(rating="up", question="", answer="a")
    with pytest.raises(ValidationError):
        FeedbackRequest(rating="up", question="q", answer="a", chunk_ids=["x"] * 51)


def test_thumbs_down_becomes_a_candidate_that_needs_review() -> None:
    fb = {"id": "0f1e2d3c-aaaa-bbbb-cccc-000000000000", "question": "What is the Q3 cost of HW-FN-7701?",
          "answer": "The documents do not say.", "comment": "it is in pricing.xlsx", "chunk_ids": ["c9"],
          "config": {"ENABLE_AGENTIC_LOOP": True}, "created_at": "2026-09-25"}
    c = to_candidate(fb)
    assert c["id"] == "fb_0f1e2d3c" and c["category"] == "feedback"
    assert c["question"] == fb["question"]
    assert c["ground_truth"] == "" and c["evidence"] == []   # a human writes these; never auto-labelled
    assert c["review"]["answer_given"] == fb["answer"] and c["review"]["retrieved_chunk_ids"] == ["c9"]
