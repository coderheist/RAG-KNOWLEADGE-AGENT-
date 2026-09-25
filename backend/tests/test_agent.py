"""Unit tests for the agentic graph (Phase 4): decision steps, retry policy, and loop termination. No network."""
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.services import rag_graph
from app.services.agent_steps import (
    GradeResult,
    Groundedness,
    RouteDecision,
    build_retry_prompt,
    check_groundedness,
    classify_turn,
    grade_chunks,
    is_weak,
    keep_identifiers,
    select_from_pool,
    should_retry,
)
from app.services.retrieval_service import RetrievedChunk


class StubLLM:
    """Returns a canned instance per schema, or raises."""

    def __init__(self, **by_schema) -> None:
        self.by_schema = by_schema
        self.calls: list[str] = []

    async def __call__(self, prompt: str, schema):
        self.calls.append(schema.__name__)
        reply = self.by_schema[schema.__name__]
        if isinstance(reply, Exception):
            raise reply
        return reply


# ── router ────────────────────────────────────────────────────────────────────────────────────

async def test_router_returns_the_models_route() -> None:
    llm = StubLLM(RouteDecision=RouteDecision(route="chitchat"))
    assert await classify_turn("hello!", [], llm) == "chitchat"


async def test_router_failure_falls_back_to_retrieval() -> None:
    llm = StubLLM(RouteDecision=RuntimeError("429"))
    assert await classify_turn("hello!", [], llm) == "needs_retrieval"


# ── grading ───────────────────────────────────────────────────────────────────────────────────

async def test_grade_chunks_passes_grades_through() -> None:
    llm = StubLLM(GradeResult=GradeResult(grades=["relevant", "irrelevant"]))
    assert await grade_chunks("q", ["a", "b"], llm) == ["relevant", "irrelevant"]


@pytest.mark.parametrize("reply", [GradeResult(grades=["relevant"]), RuntimeError("boom")])
async def test_grade_chunks_fails_open_to_keeping_every_chunk(reply) -> None:
    assert await grade_chunks("q", ["a", "b"], StubLLM(GradeResult=reply)) == ["relevant", "relevant"]


async def test_grade_chunks_with_no_chunks_makes_no_call() -> None:
    llm = StubLLM()
    assert await grade_chunks("q", [], llm) == []
    assert llm.calls == []


@pytest.mark.parametrize(
    ("grades", "min_relevant", "weak"),
    [
        ([], 1, True),
        (["irrelevant"] * 3, 1, True),
        (["partial", "partial"], 1, True),                        # related context is not evidence
        (["relevant", "irrelevant", "irrelevant"], 1, False),     # a single-fact answer needs one relevant chunk
        (["relevant", "irrelevant", "irrelevant"], 2, True),      # ...but a stricter setting does retry
        (["relevant", "relevant", "irrelevant"], 2, False),
    ],
)
def test_is_weak(grades, min_relevant, weak) -> None:
    assert is_weak(grades, min_relevant) is weak


def test_select_from_pool_prefers_relevant_across_attempts() -> None:
    pool = [("a", "irrelevant"), ("b", "partial"), ("c", "irrelevant"), ("d", "relevant"), ("b", "irrelevant")]
    assert select_from_pool(pool, top_k=5) == ["d", "b"]      # a good first-attempt chunk survives the retry
    assert select_from_pool(pool, top_k=1) == ["d"]


def test_select_from_pool_falls_back_to_everything_when_nothing_is_usable() -> None:
    pool = [("a", "irrelevant"), ("b", "irrelevant"), ("a", "irrelevant")]
    assert select_from_pool(pool, top_k=5) == ["a", "b"]      # never generate from an empty context


def test_keep_identifiers_restores_dropped_codes() -> None:
    q = "What is the Q3 unit cost for SKU HW-FN-7701?"
    assert keep_identifiers(q, "HW-FN-7701 Q3 expenses") == "HW-FN-7701 Q3 expenses"
    assert keep_identifiers(q, "quarterly fan pricing") == "quarterly fan pricing HW-FN-7701"
    both = keep_identifiers("What does E-4292 mean in v4.4.2?", "queue quota error")
    assert both == "queue quota error E-4292 v4.4.2"
    assert keep_identifiers("How long is data retained?", "retention period") == "retention period"


@pytest.mark.parametrize(
    ("weak", "attempts", "retry"),
    [(True, 1, True), (True, 2, True), (True, 3, False), (False, 1, False)],
)
def test_should_retry_stops_at_the_cap(weak, attempts, retry) -> None:
    assert should_retry(weak, attempts, max_loops=2) is retry


def test_retry_prompt_lists_the_failed_queries() -> None:
    prompt = build_retry_prompt("his skills?", [HumanMessage(content="Tell me about Marcus")], ["marcus skills"])
    assert "marcus skills" in prompt and "his skills?" in prompt


# ── groundedness ──────────────────────────────────────────────────────────────────────────────

async def test_groundedness_returns_the_verdict_or_none_on_failure() -> None:
    ok = StubLLM(Groundedness=Groundedness(grounded=False, unsupported_claims=["x"]))
    verdict = await check_groundedness("answer", ["passage"], ok)
    assert verdict is not None and verdict.grounded is False
    assert await check_groundedness("answer", ["passage"], StubLLM(Groundedness=RuntimeError("boom"))) is None


# ── graph: loop termination and the no-retrieval route ─────────────────────────────────────────

def chunk(text: str = "some passage", chunk_id: str = "c0") -> RetrievedChunk:
    return RetrievedChunk(document_id="d", filename="f.md", page_number=1, chunk_index=0, text=text, score=0.9,
                          chunk_id=chunk_id)


@pytest.fixture
def graph_env(monkeypatch: pytest.MonkeyPatch):
    """Patch the graph's nodes so no model, database or vector store is touched; count retrievals."""
    calls = {"retrieve": 0, "direct": 0}
    settings = SimpleNamespace(
        ENABLE_AGENTIC_LOOP=True, MAX_RETRIEVAL_LOOPS=2, MIN_RELEVANT_CHUNKS=1, ENABLE_GROUNDEDNESS_CHECK=False,
        ENABLE_QUERY_REWRITE=False,
    )
    monkeypatch.setattr(rag_graph, "get_settings", lambda: settings)

    async def fake_rewrite(state):
        return {"search_query": f"query attempt {state['retrieval_attempt']}", "rewrite_applied": False}

    async def fake_retrieve(state):
        calls["retrieve"] += 1
        n = state["retrieval_attempt"]
        return {"chunks": [chunk(chunk_id=f"a{n}-0"), chunk(chunk_id=f"a{n}-1")], "sources": [], "timings_ms": {},
                "retrieval_attempt": state["retrieval_attempt"] + 1}

    async def fake_generate(state):
        return {"answer": "final answer"}

    async def fake_direct(state):
        calls["direct"] += 1
        return {"answer": "hello!", "chunks": [], "sources": []}

    async def fake_save(state):
        return {}

    monkeypatch.setattr(rag_graph, "_rewrite_query_node", fake_rewrite)
    monkeypatch.setattr(rag_graph, "_retrieve_node", fake_retrieve)
    monkeypatch.setattr(rag_graph, "_generate_node", fake_generate)
    monkeypatch.setattr(rag_graph, "_direct_response_node", fake_direct)
    monkeypatch.setattr(rag_graph, "_save_history_node", fake_save)
    return calls


def initial_state() -> dict:
    return {
        "query": "what is the rate limit?", "search_query": "what is the rate limit?", "rewrite_applied": False,
        "conversation_id": "c", "history_messages": [AIMessage(content="hi")], "top_k": 5, "chunks": [],
        "sources": [], "timings_ms": {}, "route": "needs_retrieval", "retrieval_attempt": 0,
        "retrieval_weak": False, "chunk_grades": [], "failed_queries": [], "pool": [], "groundedness": {}, "answer": "",
    }


async def test_loop_terminates_at_the_cap_even_when_grading_is_always_weak(graph_env, monkeypatch) -> None:
    llm = StubLLM(RouteDecision=RouteDecision(route="needs_retrieval"),
                  GradeResult=GradeResult(grades=["irrelevant", "irrelevant"]))
    monkeypatch.setattr(rag_graph, "_agent_llm", lambda: llm)

    final = await rag_graph._compile_graph().ainvoke(initial_state())

    assert graph_env["retrieve"] == 3                    # first retrieval + MAX_RETRIEVAL_LOOPS (2) retries, then stop
    assert final["answer"] == "final answer"
    # Nothing graded usable in any attempt: generate from what was retrieved (capped at top_k) rather than
    # from an empty context -- graders misjudge look-alike identifiers, and the generator can still refuse.
    assert [c.chunk_id for c in final["chunks"]] == ["a0-0", "a0-1", "a1-0", "a1-1", "a2-0"]
    assert [s["chunk_id"] for s in final["sources"]] == [c.chunk_id for c in final["chunks"]]
    assert len(final["failed_queries"]) == 2


async def test_good_retrieval_generates_without_retrying(graph_env, monkeypatch) -> None:
    llm = StubLLM(RouteDecision=RouteDecision(route="needs_retrieval"),
                  GradeResult=GradeResult(grades=["relevant", "irrelevant"]))
    monkeypatch.setattr(rag_graph, "_agent_llm", lambda: llm)

    final = await rag_graph._compile_graph().ainvoke(initial_state())

    assert graph_env["retrieve"] == 1
    assert [c.chunk_id for c in final["chunks"]] == ["a0-0"]   # only the relevant chunk, and sources match it
    assert [s["chunk_id"] for s in final["sources"]] == ["a0-0"]


async def test_chitchat_makes_zero_retrieval_calls(graph_env, monkeypatch) -> None:
    llm = StubLLM(RouteDecision=RouteDecision(route="chitchat"))
    monkeypatch.setattr(rag_graph, "_agent_llm", lambda: llm)

    final = await rag_graph._compile_graph().ainvoke(initial_state())

    assert graph_env["retrieve"] == 0
    assert graph_env["direct"] == 1
    assert final["answer"] == "hello!"


async def test_agentic_loop_off_is_the_linear_pipeline_with_no_helper_llm_calls(graph_env, monkeypatch) -> None:
    rag_graph.get_settings().ENABLE_AGENTIC_LOOP = False
    llm = StubLLM()                                       # any call would raise KeyError
    monkeypatch.setattr(rag_graph, "_agent_llm", lambda: llm)

    final = await rag_graph._compile_graph().ainvoke(initial_state())

    assert graph_env["retrieve"] == 1
    assert llm.calls == []
    assert final["answer"] == "final answer"


async def test_a_good_first_hit_survives_a_retry(graph_env, monkeypatch) -> None:
    grades = iter([["partial", "irrelevant"], ["irrelevant", "irrelevant"], ["irrelevant", "irrelevant"]])

    class SeqLLM(StubLLM):
        async def __call__(self, prompt, schema):
            if schema is GradeResult:
                return GradeResult(grades=next(grades))
            return await super().__call__(prompt, schema)

    llm = SeqLLM(RouteDecision=RouteDecision(route="needs_retrieval"))
    monkeypatch.setattr(rag_graph, "_agent_llm", lambda: llm)

    final = await rag_graph._compile_graph().ainvoke(initial_state())

    assert graph_env["retrieve"] == 3
    assert [c.chunk_id for c in final["chunks"]] == ["a0-0"]   # the first attempt's partial hit is kept
