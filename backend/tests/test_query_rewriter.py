"""Unit tests for query rewriting (Phase 2). The LLM is a stub; no network."""
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.services.query_rewriter import format_history, guard_rewrite, rewrite_query

HISTORY = [
    HumanMessage(content="Summarize Marcus Bell's resume."),
    AIMessage(content="Marcus Bell is a Senior Backend Engineer based in Austin (resume_marcus_bell.docx, p. 1)."),
]


class StubLLM:
    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


async def test_empty_history_is_passthrough_without_llm_call() -> None:
    llm = StubLLM("should never be used")
    assert await rewrite_query("what are his skills?", [], llm) == ("what are his skills?", False)
    assert llm.prompts == []


async def test_pronoun_is_resolved_using_history() -> None:
    llm = StubLLM("What are Marcus Bell's technical skills?")
    search_query, applied = await rewrite_query("what are his skills?", HISTORY, llm)
    assert (search_query, applied) == ("What are Marcus Bell's technical skills?", True)
    assert "Marcus Bell" in llm.prompts[0]
    assert "Latest question: what are his skills?" in llm.prompts[0]


@pytest.mark.parametrize(
    "bad_reply",
    [
        "",
        "   ",
        "Here is the rewritten query: What are Marcus Bell's skills?",
        "Sure! What are Marcus Bell's skills?",
        "What are Marcus Bell's skills?\nThis resolves the pronoun 'his'.",
        "x" * 500,
    ],
)
async def test_malformed_rewrite_falls_back_to_original(bad_reply: str) -> None:
    llm = StubLLM(bad_reply)
    assert await rewrite_query("what are his skills?", HISTORY, llm) == ("what are his skills?", False)


async def test_llm_failure_falls_back_to_original() -> None:
    llm = StubLLM(RuntimeError("429 quota exceeded"))
    assert await rewrite_query("what are his skills?", HISTORY, llm) == ("what are his skills?", False)


async def test_identical_rewrite_is_not_reported_as_applied() -> None:
    llm = StubLLM("What is the rate limit for Atlas Sync?")
    assert await rewrite_query("What is the rate limit for Atlas Sync?", HISTORY, llm) == (
        "What is the rate limit for Atlas Sync?",
        False,
    )


def test_guard_allows_short_pronoun_questions_to_grow_more_than_3x() -> None:
    assert guard_rewrite("his skills?", "What are Marcus Bell's technical skills?") is not None


def test_guard_strips_wrapping_quotes() -> None:
    assert guard_rewrite("his skills?", '"What are Marcus Bell\'s technical skills?"') == (
        "What are Marcus Bell's technical skills?"
    )


def test_format_history_keeps_only_the_last_turns_and_truncates_long_answers() -> None:
    history = [HumanMessage(content=f"question {i}") for i in range(10)]
    assert format_history(history, turns=2).splitlines() == [f"User: question {i}" for i in range(6, 10)]
    long = [AIMessage(content="a" * 1000)]
    assert len(format_history(long, turns=1)) == len("Assistant: ") + 400
