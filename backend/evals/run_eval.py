"""Run the golden set against the real /query endpoint and score retrieval + generation.

    python -m evals.run_eval --dataset golden_v1 --tag baseline --concurrency 4
    python -m evals.run_eval --dataset golden_v1 --tag iter_1 --compare baseline
    python -m evals.run_eval --dataset golden_v1 --tag ci --limit 20 --fail-under recall@5=0.7
    python -m evals.run_eval --dataset golden_v1 --tag quick --no-judge      # retrieval only, no LLM cost

Retrieval is scored on the chunk ids in the `sources` SSE event, so the whole HTTP path is under test.
Results are written to evals/results/<tag>_<timestamp>.json.
"""
import argparse
import asyncio
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import httpx

from evals.dataset import load_dataset
from evals.metrics import retrieval as R
from evals.metrics.generation import DEFAULT_JUDGE_MODEL, citation_accuracy, judge_answer, refusal_correctness

RESULTS_DIR = Path(__file__).parent / "results"


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(pct / 100 * len(ordered)) - 1)]


async def stream_query(
    client: httpx.AsyncClient, base_url: str, question: str, top_k: int, history: list[dict] | None = None
) -> dict:
    payload: dict = {"query": question, "top_k": top_k}
    if history:
        payload["history"] = history
    start = time.perf_counter()
    out: dict = {"answer": "", "sources": [], "conversation_id": None, "ttft_ms": None, "error": None, "rewrite": None}
    async with client.stream("POST", f"{base_url}/query", json=payload) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            kind = event.get("type")
            if kind == "sources":
                out["sources"] = event.get("sources", [])
            elif kind == "chunk":
                if out["ttft_ms"] is None:
                    out["ttft_ms"] = (time.perf_counter() - start) * 1000
                out["answer"] += event.get("content", "")
            elif kind == "done":
                out["conversation_id"] = event.get("conversation_id")
            elif kind == "query_rewrite":
                out["rewrite"] = event
            elif kind == "error":
                out["error"] = event.get("message", "unknown error")
    out["latency_ms"] = (time.perf_counter() - start) * 1000
    return out


async def query_with_retry(
    client: httpx.AsyncClient, base_url: str, question: str, top_k: int,
    history: list[dict] | None = None, need_answer: bool = True, attempts: int = 3,
) -> dict:
    """stream_query, retrying per-minute 429s. Daily-quota 429s cannot recover, so they are returned as-is."""
    run: dict = {}
    for attempt in range(attempts):
        run = await stream_query(client, base_url, question, top_k, history)
        err = run["error"] or ""
        retryable = "429" in err and "PerDay" not in err and (need_answer or not run["sources"])
        if not retryable or attempt == attempts - 1:
            return run
        match = re.search(r"retry in ([\d.]+)s", err)
        await asyncio.sleep(min(65.0, float(match.group(1)) + 1) if match else 15.0)
    return run


async def fetch_chunk_texts(
    client: httpx.AsyncClient, qdrant_url: str, collection: str, ids: list[str]
) -> dict[str, str]:
    if not ids:
        return {}
    resp = await client.post(
        f"{qdrant_url}/collections/{collection}/points", json={"ids": ids, "with_payload": True, "with_vector": False}
    )
    resp.raise_for_status()
    return {str(p["id"]): p["payload"].get("text", "") for p in resp.json()["result"]}


async def run_case(row: dict, args: argparse.Namespace, client: httpx.AsyncClient) -> dict:
    k = args.top_k
    result: dict = {
        "id": row["id"], "category": row["category"], "question": row["question"],
        "ground_truth": row["ground_truth"], "metrics": {}, "reasons": {}, "error": None,
    }
    try:
        run = await query_with_retry(
            client, args.base_url, row["question"], k, history=row["conversation_history"] or None,
            need_answer=not args.no_judge,
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    if run["error"] and not run["sources"]:
        result["error"] = run["error"][:200]
        return result
    # Sources arrive before generation, so retrieval is still scorable when generation fails (e.g. a 429).
    result["generation_error"] = run["error"][:200] if run["error"] else None

    retrieved = [s.get("chunk_id", "") for s in run["sources"]]
    relevant = set(row["relevant_chunk_ids"])
    m = result["metrics"]
    m[f"recall@{k}"] = R.recall_at_k(retrieved, relevant, k)
    m[f"precision@{k}"] = R.precision_at_k(retrieved, relevant, k)
    m["mrr"] = R.reciprocal_rank(retrieved, relevant)
    m[f"ndcg@{k}"] = R.ndcg_at_k(retrieved, relevant, k)
    m[f"hit_rate@{k}"] = R.hit_rate_at_k(retrieved, relevant, k)
    m["no_retrieval"] = (1.0 if not retrieved else 0.0) if row["category"] == "chitchat" else None

    result.update(
        answer=run["answer"], retrieved_chunk_ids=retrieved, latency_ms=run["latency_ms"], ttft_ms=run["ttft_ms"],
        rewrite=run["rewrite"],
    )

    if not args.no_judge and not run["error"]:
        try:
            await judge_case(row, run, result, args, client)
        except Exception as exc:  # one bad judge response must not abort a 60-case run
            result["judge_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    return result


async def judge_case(row: dict, run: dict, result: dict, args: argparse.Namespace, client: httpx.AsyncClient) -> None:
    texts = await fetch_chunk_texts(client, args.qdrant_url, args.collection, result["retrieved_chunk_ids"])
    contexts = [
        {
            "filename": s["filename"],
            "page_number": s["page_number"],
            "text": texts.get(s.get("chunk_id", ""), s["text_snippet"]),
        }
        for s in run["sources"]
    ]
    judged = await judge_answer(row["question"], run["answer"], contexts, args.judge_model)
    cite = await citation_accuracy(run["answer"], contexts, judged["refused"], args.judge_model)
    refusal = refusal_correctness(row["category"], judged["refused"])
    for name, scored in (
        ("faithfulness", judged["faithfulness"]), ("answer_relevance", judged["answer_relevance"]),
        ("context_precision", judged["context_precision"]), ("citation_accuracy", cite),
        ("refusal_correctness", refusal),
    ):
        result["metrics"][name] = scored.score
        result["reasons"][name] = scored.reason
    result["refused"] = judged["refused"]


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def aggregate(cases: list[dict]) -> dict:
    per_metric: dict[str, list[float]] = defaultdict(list)
    per_cat: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    latencies: list[float] = []
    ttfts: list[float] = []
    names: set[str] = set()
    for c in cases:
        if c["error"]:
            continue
        latencies.append(c["latency_ms"])
        if c["ttft_ms"] is not None:
            ttfts.append(c["ttft_ms"])
        for name, value in c["metrics"].items():
            names.add(name)
            if value is not None:
                per_metric[name].append(value)
                per_cat[c["category"]][name].append(value)

    overall = {name: mean(per_metric[name]) for name in sorted(names)}
    by_category = {cat: {n: mean(v) for n, v in sorted(ms.items())} for cat, ms in sorted(per_cat.items())}
    warnings = []
    for name in sorted(names):
        values = per_metric[name]
        if not values or overall[name] is None or math.isnan(overall[name]):
            warnings.append(f"{name}: no scorable cases / NaN - metric is broken, not perfect")
        elif len(values) >= 5 and len(set(values)) == 1:
            warnings.append(f"{name}: zero variance ({values[0]:.3f} on all {len(values)} cases) - check the metric")
    return {
        "overall": overall, "by_category": by_category,
        "latency_ms": {
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "ttft_p50": percentile(ttfts, 50),
        },
        "n_cases": len(cases), "n_errors": sum(1 for c in cases if c["error"]),
        "n_generation_errors": sum(1 for c in cases if c.get("generation_error")),
        "n_judge_errors": sum(1 for c in cases if c.get("judge_error")), "warnings": warnings,
    }


def stratified_subset(rows: list[dict], limit: int) -> list[dict]:
    """Deterministic round-robin across categories so a smoke subset still covers every category."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        buckets[r["category"]].append(r)
    picked: list[dict] = []
    while len(picked) < limit and any(buckets.values()):
        for cat in sorted(buckets):
            if buckets[cat] and len(picked) < limit:
                picked.append(buckets[cat].pop(0))
    return sorted(picked, key=lambda r: r["id"])


def load_results(tag: str) -> dict:
    files = sorted(RESULTS_DIR.glob(f"{tag}_*.json"))
    if not files:
        raise SystemExit(f"no results file found for tag {tag!r} in {RESULTS_DIR}")
    return json.loads(files[-1].read_text())


def fmt(value: float | None, digits: int = 3) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def print_summary(current: dict, tag: str, baseline: dict | None, base_tag: str | None) -> None:
    cur = {**current["overall"], "latency_p50_ms": current["latency_ms"]["p50"]}
    base = None
    if baseline:
        base = {**baseline["aggregates"]["overall"], "latency_p50_ms": baseline["aggregates"]["latency_ms"]["p50"]}
    head = f"{'Metric':22s}"
    if base is not None:
        print(f"{head}{base_tag:>12s}{tag:>12s}{'delta':>10s}")
    else:
        print(f"{head}{tag:>12s}")
    for name, value in cur.items():
        digits = 0 if name == "latency_p50_ms" else 3
        if base is not None:
            b = base.get(name)
            delta = None if (b is None or value is None) else value - b
            if delta is None:
                delta_txt = "-"
            else:
                delta_txt = ("" if delta < 0 else "+") + fmt(delta, digits)
            print(f"{name:22s}{fmt(b, digits):>12s}{fmt(value, digits):>12s}{delta_txt:>10s}")
        else:
            print(f"{name:22s}{fmt(value, digits):>12s}")


def print_by_category(current: dict) -> None:
    cats = current["by_category"]
    metrics = sorted({n for ms in cats.values() for n in ms})
    print("\nby category:")
    print(f"{'metric':22s}" + "".join(f"{c[:12]:>14s}" for c in cats))
    for name in metrics:
        print(f"{name:22s}" + "".join(f"{fmt(cats[c].get(name)):>14s}" for c in cats))


def check_fail_under(current: dict, thresholds: list[str]) -> list[str]:
    failures = []
    for spec in thresholds:
        name, _, raw = spec.partition("=")
        value = current["overall"].get(name)
        if value is None or value < float(raw):
            failures.append(f"{name}={fmt(value)} is below required {raw}")
    return failures


async def main_async(args: argparse.Namespace) -> int:
    rows = load_dataset(args.dataset)
    if args.categories:
        rows = [r for r in rows if r["category"] in args.categories.split(",")]
    if args.limit:
        rows = stratified_subset(rows, args.limit)
    unresolved = [r["id"] for r in rows if r["evidence"] and not r["relevant_chunk_ids"]]
    if unresolved:
        print(f"cases without relevant_chunk_ids (run `python -m evals.setup_corpus` first): {unresolved[:8]}")
        return 2

    sem = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(timeout=httpx.Timeout(300)) as client:
        async def guarded(row: dict) -> dict:
            async with sem:
                return await run_case(row, args, client)

        cases = await asyncio.gather(*[guarded(r) for r in rows])

    agg = aggregate(list(cases))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"{args.tag}_{stamp}.json"
    config = {
        "dataset": args.dataset, "top_k": args.top_k, "judge_model": None if args.no_judge else args.judge_model,
        "base_url": args.base_url, "limit": args.limit, "note": args.note,
    }
    payload = {"tag": args.tag, "timestamp": stamp, "config": config, "aggregates": agg, "cases": cases}
    path.write_text(json.dumps(payload, indent=2))

    baseline = load_results(args.compare) if args.compare else None
    print(
        f"\n{agg['n_cases']} cases, {agg['n_errors']} errors, "
        f"{agg['n_generation_errors']} generation errors, {agg['n_judge_errors']} judge errors -> {path.name}\n"
    )
    print_summary(agg, args.tag, baseline, args.compare)
    print_by_category(agg)
    for w in agg["warnings"]:
        print(f"WARNING: {w}")
    for c in cases:
        if c["error"]:
            print(f"ERROR {c['id']}: {c['error'].splitlines()[0]}")
    gen_errors = [c for c in cases if c.get("generation_error")]
    if gen_errors:
        print(f"GENERATION FAILED on {len(gen_errors)} cases, e.g. {gen_errors[0]['generation_error'].splitlines()[0]}")

    failures = check_fail_under(agg, args.fail_under or [])
    for f in failures:
        print(f"FAIL: {f}")
    generation_broke_judging = agg["n_generation_errors"] and not args.no_judge
    return 1 if failures or agg["n_errors"] or generation_broke_judging else 0


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="golden_v1")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--compare", help="tag of an earlier results file to diff against")
    ap.add_argument(
        "--fail-under", action="append", metavar="METRIC=VALUE", help="exit non-zero if an overall metric is lower"
    )
    ap.add_argument("--limit", type=int, help="stratified subset size (e.g. 20 for CI smoke)")
    ap.add_argument("--categories", help="comma-separated category filter")
    ap.add_argument("--no-judge", action="store_true", help="skip LLM-judged metrics (retrieval only)")
    ap.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    ap.add_argument("--note", default="", help="free-text note stored in the results file")
    ap.add_argument("--base-url", default=os.environ.get("EVAL_BASE_URL", "http://localhost:8000"))
    ap.add_argument("--qdrant-url", default=os.environ.get("EVAL_QDRANT_URL", "http://localhost:6333"))
    ap.add_argument("--collection", default=os.environ.get("QDRANT_COLLECTION", "documents"))
    return ap.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async(parse_args())))
