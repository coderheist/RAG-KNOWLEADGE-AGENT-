"""LLM-as-judge generation metrics (Gemini, temperature 0), with an on-disk cache.

Each metric is a 0-1 score plus a short reason. Judge calls are cached by a hash of their
full prompt in evals/.cache/, so re-running an unchanged config costs nothing.

To stay inside free-tier Gemini limits one structured call scores faithfulness, answer
relevance, context precision and refusal together; citation support is a second call.
"""
import asyncio
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
# Quotas are per model, and older flash models are unavailable to newer accounts; override with EVAL_JUDGE_MODEL.
DEFAULT_JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "gemini-flash-lite-latest")

# Matches "(report.pdf, p. 7)" and "(a.md, p. 1)" style citations.
CITATION_RE = re.compile(r"\(([^(),]+\.[A-Za-z0-9]+),\s*p\.\s*(\d+)\)")

_MAIN_PROMPT = """You are a strict evaluator of a retrieval-augmented answer. Reply with JSON only.

QUESTION:
{question}

RETRIEVED CONTEXT (numbered chunks):
{context}

ANSWER:
{answer}

Score each field from 0.0 to 1.0 and give a one-sentence reason:
- faithfulness: fraction of the answer's factual claims that are supported by the retrieved context (1.0 if the answer makes no factual claims beyond a refusal).
- answer_relevance: does the answer directly address the question that was asked?
- context_precision: fraction of the retrieved chunks that were actually useful for the answer (0.0 if no chunks were retrieved).
- refused: true if the answer declines to answer or says the information is not available, false otherwise.

JSON shape: {{"faithfulness": {{"score": 0.0, "reason": ""}}, "answer_relevance": {{"score": 0.0, "reason": ""}}, "context_precision": {{"score": 0.0, "reason": ""}}, "refused": false}}"""

_CITATION_PROMPT = """You verify citations. For each numbered item, decide whether the cited chunk text supports the claim it is attached to. Reply with JSON only.

{items}

JSON shape: {{"verdicts": [{{"id": 1, "supported": true, "reason": ""}}]}}"""


@dataclass
class Scored:
    score: float | None
    reason: str = ""


def _cache_path(prompt: str, model: str) -> Path:
    return CACHE_DIR / f"{hashlib.sha256((model + prompt).encode()).hexdigest()}.json"


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


def _generate(prompt: str, model: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    response = genai.GenerativeModel(model).generate_content(
        prompt,
        generation_config={"temperature": 0, "response_mime_type": "application/json"},
    )
    return response.text


async def _judge_json(prompt: str, model: str, retries: int = 5) -> dict:
    path = _cache_path(prompt, model)
    if path.exists():
        return json.loads(path.read_text())
    delay = 4.0
    for attempt in range(retries):
        try:
            result = _parse_json(await asyncio.to_thread(_generate, prompt, model))
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result))
            return result
        except Exception:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def format_context(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"[{i}] ({c['filename']}, p. {c['page_number']})\n{c['text']}" for i, c in enumerate(chunks, 1)
    ) or "(none)"


def extract_citations(answer: str) -> list[tuple[str, int, str]]:
    """(filename, page, claim_sentence) for every citation in the answer."""
    out = []
    for m in CITATION_RE.finditer(answer):
        start = max(answer.rfind("\n", 0, m.start()), answer.rfind(". ", 0, m.start()))
        claim = answer[start + 1 : m.start()].strip(" .-*\n")
        out.append((m.group(1).strip(), int(m.group(2)), claim))
    return out


async def judge_answer(question: str, answer: str, chunks: list[dict], model: str = DEFAULT_JUDGE_MODEL) -> dict:
    """faithfulness / answer_relevance / context_precision as Scored, plus refused: bool."""
    prompt = _MAIN_PROMPT.format(question=question, context=format_context(chunks), answer=answer)
    raw = await _judge_json(prompt, model)
    if not isinstance(raw, dict):
        raise ValueError(f"judge returned {type(raw).__name__}, expected a JSON object")

    def field(name: str) -> Scored:
        item = raw.get(name) or {}
        score = item.get("score")
        return Scored(float(score) if score is not None else None, str(item.get("reason", "")))

    return {
        "faithfulness": field("faithfulness"),
        "answer_relevance": field("answer_relevance"),
        "context_precision": field("context_precision"),
        "refused": bool(raw.get("refused", False)),
    }


async def citation_accuracy(
    answer: str, chunks: list[dict], refused: bool, model: str = DEFAULT_JUDGE_MODEL, applicable: bool = True
) -> Scored:
    """Share of citations that both exist in the retrieved set and support their claim.

    None when not applicable (chitchat: nothing to cite) or for refusals. An otherwise answerable question
    whose answer has no citations at all scores 0.0.
    """
    if not applicable:
        return Scored(None, "not applicable - no factual claims expected")
    if refused:
        return Scored(None, "refusal - no citations expected")
    citations = extract_citations(answer)
    if not citations:
        return Scored(0.0, "answer contains no (file, p. N) citations")

    by_key: dict[tuple[str, int], list[str]] = {}
    for c in chunks:
        by_key.setdefault((c["filename"], int(c["page_number"])), []).append(c["text"])

    supported = 0
    to_check: list[tuple[int, str, str]] = []
    for i, (filename, page, claim) in enumerate(citations, 1):
        texts = by_key.get((filename, page))
        if texts:
            to_check.append((i, claim, "\n".join(texts)))
    if to_check:
        items = "\n\n".join(f"{i}. CLAIM: {claim}\n   CITED CHUNK TEXT: {text}" for i, claim, text in to_check)
        raw = await _judge_json(_CITATION_PROMPT.format(items=items), model)
        verdicts = raw if isinstance(raw, list) else raw.get("verdicts", [])   # models return either shape
        supported = sum(1 for v in verdicts if isinstance(v, dict) and v.get("supported"))
    missing = len(citations) - len(to_check)
    reason = f"{supported}/{len(citations)} citations supported; {missing} cite a source that was not retrieved"
    return Scored(supported / len(citations), reason)


def refusal_correctness(category: str, refused: bool) -> Scored:
    """1.0 iff the model refused exactly on unanswerable questions and nowhere else."""
    should_refuse = category == "unanswerable"
    ok = refused == should_refuse
    return Scored(1.0 if ok else 0.0, f"refused={refused}, expected={should_refuse}")
