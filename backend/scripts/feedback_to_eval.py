"""Turn thumbs-down feedback into golden-set candidates for human review (Phase 6 feedback loop).

    python scripts/feedback_to_eval.py [--since 2026-09-01] [--out evals/datasets/candidates/feedback.jsonl]

Each candidate is shaped like a golden_v1.jsonl row, with the fields a reviewer must fill left empty:
`ground_truth` and `evidence` (then run `python -m evals.setup_corpus` to derive relevant_chunk_ids from the
evidence). The answer that was given, the user's comment and the chunks it saw are kept under `review` so the
reviewer can see what went wrong. Candidates never enter the golden set automatically: a wrong label in the
eval set is worse than a missing one. Rows already exported (same feedback id) are skipped on re-runs.

production failure -> candidate -> reviewed golden case -> fix -> measured improvement
"""
import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.db.feedback_models import Feedback
from app.db.postgres import get_db_session

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "evals" / "datasets" / "candidates" / "feedback.jsonl"


def to_candidate(fb: dict) -> dict:
    """One thumbs-down feedback row -> one golden-set candidate awaiting review."""
    return {
        "id": f"fb_{str(fb['id'])[:8]}",
        "question": fb["question"],
        "ground_truth": "",
        "evidence": [],
        "relevant_chunk_ids": [],
        "source_documents": [],
        "category": "feedback",
        "difficulty": "unknown",
        "conversation_history": [],
        "review": {
            "feedback_id": str(fb["id"]),
            "answer_given": fb["answer"],
            "comment": fb.get("comment"),
            "retrieved_chunk_ids": fb.get("chunk_ids", []),
            "config": fb.get("config", {}),
            "created_at": str(fb.get("created_at", "")),
        },
    }


async def main(since: datetime | None, out: Path) -> None:
    stmt = select(Feedback).where(Feedback.rating == "down").order_by(Feedback.created_at)
    if since:
        stmt = stmt.where(Feedback.created_at >= since)
    async with get_db_session() as session:
        rows = (await session.execute(stmt)).scalars().all()

    out.parent.mkdir(parents=True, exist_ok=True)
    lines = out.read_text(encoding="utf-8").splitlines() if out.exists() else []
    done = {json.loads(line)["review"]["feedback_id"] for line in lines if line}
    new = [to_candidate(vars(r)) for r in rows if str(r.id) not in done]
    with out.open("a", encoding="utf-8") as f:
        for c in new:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{len(rows)} thumbs-down rows, {len(new)} new candidates -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", type=datetime.fromisoformat, help="only feedback on/after this date")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    asyncio.run(main(args.since, args.out))
