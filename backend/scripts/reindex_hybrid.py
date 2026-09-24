"""Backfill BM25 sparse vectors for chunks indexed before hybrid search existed.

Dense vectors are NOT recomputed, so this costs no embedding API calls. Resumable: every point that
gets a sparse vector is flagged with payload `has_sparse=true`, and only unflagged points are scanned,
so an interrupted run simply continues where it stopped.

    python scripts/reindex_hybrid.py [--batch-size 64] [--dry-run]
"""
import argparse
import asyncio

from qdrant_client.http import models as qmodels

from app.config import get_settings
from app.db.qdrant import get_qdrant_client
from app.services.vector_service import attach_sparse_vectors, ensure_collection

_PENDING = qmodels.Filter(must_not=[qmodels.FieldCondition(key="has_sparse", match=qmodels.MatchValue(value=True))])


async def main(batch_size: int, dry_run: bool) -> None:
    client = get_qdrant_client()
    coll = get_settings().QDRANT_COLLECTION
    await ensure_collection()

    pending = (await client.count(collection_name=coll, count_filter=_PENDING, exact=True)).count
    print(f"{pending} chunks in '{coll}' still need a sparse vector")
    if dry_run or not pending:
        return

    done = 0
    while True:
        points, _ = await client.scroll(
            collection_name=coll, scroll_filter=_PENDING, limit=batch_size, with_payload=["text"], with_vectors=False
        )
        if not points:
            break
        pairs = [(str(p.id), (p.payload or {}).get("text", "")) for p in points]
        done += await attach_sparse_vectors(pairs, batch_size)
        print(f"  {done}/{pending}")
    print("done")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    asyncio.run(main(args.batch_size, args.dry_run))
