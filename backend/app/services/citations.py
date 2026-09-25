"""
Verified citations (Phase 4).

Today citations exist only because the system prompt asks for them, so nothing checks that
``(report.pdf, p. 7)`` is real. In structured mode the model returns
``{"answer", "claims": [{"text", "source_ids"}], "confidence"}`` and every source id is validated against the
chunks actually retrieved before anything leaves the API; invented ids are dropped.

Streaming still works: ``AnswerStreamExtractor`` pulls the text of the ``"answer"`` field out of the
growing JSON token by token, and the validated claims are emitted once the response is complete.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.utils.logging import get_logger

logger = get_logger(__name__)

INLINE_CITATION_RE = re.compile(r"\(([^(),]+\.[A-Za-z0-9]+),\s*p\.\s*(\d+)\)")

STRUCTURED_OUTPUT_INSTRUCTIONS = """

── OUTPUT FORMAT ───────────────────────────────────────────────────────────────
Respond with ONE JSON object and nothing else, with the keys in exactly this order:
{"answer": "<your answer, keeping the inline (filename, p. N) citations>",
 "claims": [{"text": "<one factual claim from the answer>", "source_ids": [<numbers of the [Source N] blocks that support it>]}],
 "confidence": "high" | "medium" | "low"}
Use only [Source N] numbers that appear above. If the documents do not contain the answer, give a short answer
saying so, an empty "claims" list, and confidence "low"."""


class Claim(BaseModel):
    text: str
    source_ids: list[int] = Field(default_factory=list)


class StructuredAnswer(BaseModel):
    answer: str
    claims: list[Claim] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


def parse_structured_answer(raw: str) -> StructuredAnswer | None:
    """The model's JSON, or None if it is not valid structured output (callers fall back to plain text)."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        return StructuredAnswer.model_validate_json(text)
    except ValidationError:
        return None


def validate_claims(claims: list[Claim], n_sources: int) -> tuple[list[Claim], int]:
    """Drop source ids that do not refer to a retrieved chunk. Returns (claims, number of ids dropped)."""
    dropped = 0
    cleaned: list[Claim] = []
    for claim in claims:
        valid = sorted({i for i in claim.source_ids if 1 <= i <= n_sources})
        dropped += len(set(claim.source_ids)) - len(valid)
        cleaned.append(Claim(text=claim.text, source_ids=valid))
    return cleaned, dropped


def find_invalid_inline_citations(answer: str, retrieved: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Inline ``(file, p. N)`` citations that do not match any retrieved (filename, page)."""
    known = set(retrieved)
    return [
        (name.strip(), int(page))
        for name, page in INLINE_CITATION_RE.findall(answer)
        if (name.strip(), int(page)) not in known
    ]


_ANSWER_START = re.compile(r'"answer"\s*:\s*"')
_SIMPLE_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", '"': '"', "\\": "\\", "/": "/"}


class AnswerStreamExtractor:
    """
    Incrementally extracts the decoded text of the top-level ``"answer"`` string from streamed JSON.

    ``feed(chunk)`` returns whatever new answer text became available. Escape sequences that straddle a chunk
    boundary are held back until complete. ``started`` is False if the output never looked like structured
    JSON, so the caller can fall back to emitting the whole answer at the end.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._pos = 0
        self.started = False
        self.finished = False

    def feed(self, chunk: str) -> str:
        if self.finished:
            return ""
        self._buffer += chunk
        if not self.started:
            match = _ANSWER_START.search(self._buffer)
            if not match:
                return ""
            self.started = True
            self._pos = match.end()

        out: list[str] = []
        buf = self._buffer
        i = self._pos
        while i < len(buf):
            ch = buf[i]
            if ch == '"':
                self.finished = True
                i += 1
                break
            if ch != "\\":
                out.append(ch)
                i += 1
                continue
            if i + 1 >= len(buf):
                break                                   # lone backslash at the end of the chunk: wait
            esc = buf[i + 1]
            if esc == "u":
                if i + 6 > len(buf):
                    break                               # \uXXXX not complete yet
                try:
                    out.append(chr(int(buf[i + 2 : i + 6], 16)))
                except ValueError:
                    out.append(buf[i : i + 6])
                i += 6
            else:
                out.append(_SIMPLE_ESCAPES.get(esc, esc))
                i += 2
        self._pos = i
        return "".join(out)
