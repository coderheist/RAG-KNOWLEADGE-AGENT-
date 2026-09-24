"""Golden dataset loading and validation."""
import json
from pathlib import Path

from evals.build_corpus import corpus_texts

DATASETS_DIR = Path(__file__).parent / "datasets"
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "test_files"
FIXTURE_DOCS = ["test.csv", "test.md", "test.txt"]

CATEGORIES = {"factual_lookup", "multi_hop", "exact_term", "follow_up", "unanswerable", "chitchat"}
NO_EVIDENCE_CATEGORIES = {"unanswerable", "chitchat"}
REQUIRED_KEYS = {
    "id", "question", "ground_truth", "evidence", "relevant_chunk_ids",
    "source_documents", "category", "difficulty", "conversation_history",
}


def normalize(text: str) -> str:
    """Collapse whitespace so evidence matches across PDF/markdown line wrapping."""
    return " ".join(text.split())


def load_dataset(name: str) -> list[dict]:
    path = DATASETS_DIR / f"{name}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_dataset(name: str, rows: list[dict]) -> None:
    path = DATASETS_DIR / f"{name}.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def document_texts() -> dict[str, str]:
    """Normalized plain text of every document a gold evidence string may live in."""
    texts = {name: normalize(text) for name, text in corpus_texts().items()}
    for name in FIXTURE_DOCS:
        texts[name] = normalize((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    return texts


def validate(rows: list[dict]) -> list[str]:
    """Return a list of human-readable problems (empty means the dataset is sound)."""
    problems: list[str] = []
    texts = document_texts()
    seen: set[str] = set()

    for row in rows:
        rid = row.get("id", "<missing id>")
        missing = REQUIRED_KEYS - row.keys()
        if missing:
            problems.append(f"{rid}: missing keys {sorted(missing)}")
            continue
        if rid in seen:
            problems.append(f"{rid}: duplicate id")
        seen.add(rid)
        if row["category"] not in CATEGORIES:
            problems.append(f"{rid}: unknown category {row['category']!r}")
        if row["category"] == "follow_up" and not row["conversation_history"]:
            problems.append(f"{rid}: follow_up case has no conversation_history")
        if row["category"] != "follow_up" and row["conversation_history"]:
            problems.append(f"{rid}: only follow_up cases may carry conversation_history")

        if row["category"] in NO_EVIDENCE_CATEGORIES:
            if row["evidence"] or row["source_documents"]:
                problems.append(f"{rid}: {row['category']} case must have no evidence or source_documents")
            continue
        if not row["evidence"]:
            problems.append(f"{rid}: answerable case has no evidence")
        for ev in row["evidence"]:
            homes = [name for name, text in texts.items() if normalize(ev) in text]
            if len(homes) != 1:
                problems.append(f"{rid}: evidence {ev!r} found in {len(homes)} documents {homes}, expected exactly 1")
            elif homes[0] not in row["source_documents"]:
                problems.append(f"{rid}: evidence {ev!r} lives in {homes[0]}, not listed in source_documents")
    return problems
