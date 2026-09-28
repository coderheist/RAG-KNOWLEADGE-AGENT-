"""Unit tests for Langfuse tracing (Phase 6): off by default, flag-tagged traces, and fail-open behaviour."""
from types import SimpleNamespace

from app.services import tracing


def settings(**over):
    base = dict(
        LANGFUSE_ENABLED=True, LANGFUSE_PUBLIC_KEY="pk", LANGFUSE_SECRET_KEY="sk", LANGFUSE_HOST="http://x",
        GEMINI_MODEL="m", ENABLE_QUERY_REWRITE=True, ENABLE_HYBRID_SEARCH=True, ENABLE_RERANKING=False,
        ENABLE_AGENTIC_LOOP=True, ENABLE_GROUNDEDNESS_CHECK=False, ENABLE_VERIFIED_CITATIONS=False,
    )
    return SimpleNamespace(**{**base, **over})


class FakeClient:
    def __init__(self) -> None:
        self.kwargs: dict = {}

    def trace(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(get_langchain_handler=lambda update_parent: "handler", update=lambda **kw: None)


def test_disabled_or_keyless_means_no_trace(monkeypatch) -> None:
    def boom():
        raise AssertionError("the Langfuse client must not be created when tracing is off")

    monkeypatch.setattr(tracing, "_client", boom)
    for s in (settings(LANGFUSE_ENABLED=False), settings(LANGFUSE_SECRET_KEY="")):
        monkeypatch.setattr(tracing, "get_settings", lambda s=s: s)
        assert tracing.start_trace("q", "c") is None
    assert tracing.langchain_callbacks(None) == []
    tracing.end_trace(None, "a", {})                                  # no-op, no error


def test_trace_is_tagged_with_flags_and_session(monkeypatch) -> None:
    client = FakeClient()
    monkeypatch.setattr(tracing, "get_settings", settings)
    monkeypatch.setattr(tracing, "_client", lambda: client)

    trace = tracing.start_trace("what is x?", "conv-1")

    assert trace is not None and tracing.langchain_callbacks(trace) == ["handler"]
    assert client.kwargs["session_id"] == "conv-1" and client.kwargs["input"] == "what is x?"
    assert "agentic_loop:on" in client.kwargs["tags"] and "reranking:off" in client.kwargs["tags"]
    assert client.kwargs["metadata"]["GEMINI_MODEL"] == "m"


def test_tracing_failures_never_raise(monkeypatch) -> None:
    def broken():
        raise ConnectionError("langfuse is down")

    monkeypatch.setattr(tracing, "get_settings", settings)
    monkeypatch.setattr(tracing, "_client", broken)
    assert tracing.start_trace("q", "c") is None

    bad = SimpleNamespace(get_langchain_handler=broken, update=lambda **kw: broken())
    assert tracing.langchain_callbacks(bad) == []
    tracing.end_trace(bad, "a", {})
