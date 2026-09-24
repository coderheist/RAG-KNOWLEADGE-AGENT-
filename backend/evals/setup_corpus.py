"""Build the eval corpus, index it through the real API, and derive relevant_chunk_ids from Qdrant.

    python -m evals.setup_corpus --dataset golden_v1 [--base-url http://localhost:8000]
                                 [--qdrant-url http://localhost:6333] [--collection documents]

Gold labels are the `evidence` strings in the dataset; chunk ids are *derived* from whichever
indexed chunks contain that evidence, so re-running this after a chunking change re-labels
everything without hand edits.
"""
import argparse
import os
import sys
from collections import Counter

import httpx

from evals.build_corpus import build
from evals.dataset import FIXTURE_DIR, FIXTURE_DOCS, load_dataset, normalize, validate, write_dataset


def upload(client: httpx.Client, base_url: str, path) -> str:
    with path.open("rb") as f:
        resp = client.post(f"{base_url}/upload", files={"files": (path.name, f, "application/octet-stream")})
    resp.raise_for_status()
    doc = resp.json()["documents"][0]
    if doc["status"] not in ("completed", "already_exists"):
        raise RuntimeError(f"upload of {path.name} failed: {doc}")
    return doc["status"]


def fetch_chunks(client: httpx.Client, qdrant_url: str, collection: str) -> list[dict]:
    chunks: list[dict] = []
    offset = None
    while True:
        body = {"limit": 256, "with_payload": True, "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        resp = client.post(f"{qdrant_url}/collections/{collection}/points/scroll", json=body)
        resp.raise_for_status()
        result = resp.json()["result"]
        chunks.extend({"id": str(p["id"]), **p["payload"]} for p in result["points"])
        offset = result.get("next_page_offset")
        if offset is None:
            return chunks


def resolve(rows: list[dict], chunks: list[dict]) -> list[str]:
    """Fill relevant_chunk_ids in place; return problems for evidence no chunk contains."""
    problems: list[str] = []
    for row in rows:
        ids: set[str] = set()
        for ev in row["evidence"]:
            hits = [
                c["id"] for c in chunks
                if c["filename"] in row["source_documents"] and normalize(ev) in normalize(c["text"])
            ]
            if not hits:
                problems.append(
                    f"{row['id']}: evidence {ev!r} is not contained in any indexed chunk of {row['source_documents']}"
                )
            ids.update(hits)
        row["relevant_chunk_ids"] = sorted(ids)
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="golden_v1")
    ap.add_argument("--base-url", default=os.environ.get("EVAL_BASE_URL", "http://localhost:8000"))
    ap.add_argument("--qdrant-url", default=os.environ.get("EVAL_QDRANT_URL", "http://localhost:6333"))
    ap.add_argument("--collection", default=os.environ.get("QDRANT_COLLECTION", "documents"))
    args = ap.parse_args()

    rows = load_dataset(args.dataset)
    problems = validate(rows)
    if problems:
        print("dataset invalid:\n  " + "\n  ".join(problems))
        return 1

    paths = build() + [FIXTURE_DIR / name for name in FIXTURE_DOCS]
    with httpx.Client(timeout=300) as client:
        for path in paths:
            print(f"{path.name:32s} {upload(client, args.base_url, path)}")
        chunks = fetch_chunks(client, args.qdrant_url, args.collection)

    wanted = {p.name for p in paths}
    per_doc = Counter(c["filename"] for c in chunks if c["filename"] in wanted)
    print(f"\nindexed chunks per document ({sum(per_doc.values())} total):")
    for name, n in sorted(per_doc.items()):
        print(f"  {name:32s} {n}")

    problems = resolve(rows, chunks)
    if problems:
        print("\nunresolved evidence:\n  " + "\n  ".join(problems))
        return 1
    write_dataset(args.dataset, rows)
    labelled = sum(1 for r in rows if r["relevant_chunk_ids"])
    print(f"\nresolved relevant_chunk_ids for {labelled} cases in {args.dataset}.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
