"""Migrate an existing dense-only collection to one that supports hybrid search.

Qdrant cannot add a new (sparse) vector name to an existing collection, so this copies every point into a
NEW collection that has the BM25 sparse vector configured, and computes the sparse vectors locally. Dense
vectors and payloads are copied as-is: no re-embedding, so no embedding API calls. The source collection is
never modified. Resumable: points already in the target are skipped, and any that lack a sparse vector
(e.g. an interrupted run) get one.

    python scripts/reindex_hybrid.py --target documents_hybrid [--batch-size 64] [--dry-run]

Then run the API with QDRANT_COLLECTION=documents_hybrid (and ENABLE_HYBRID_SEARCH=true).
"""
import argparse
import asyncio

from qdrant_client.http import models as qmodels

from app.config import get_settings
from app.db.qdrant import get_qdrant_client
from app.services.vector_service import _SPARSE_CONFIG, attach_sparse_vectors


async def main(target: str, batch_size: int, dry_run: bool) -> None:
    client = get_qdrant_client()
    source = get_settings().QDRANT_COLLECTION
    if target == source:
        raise SystemExit("--target must differ from the source collection")

    total = (await client.count(collection_name=source, exact=True)).count
    print(f"{total} points in source '{source}' -> target '{target}'")
    if dry_run:
        return

    existing = {c.name for c in (await client.get_collections()).collections}
    if target not in existing:
        info = await client.get_collection(source)
        await client.create_collection(
            collection_name=target,
            vectors_config=info.config.params.vectors,
            sparse_vectors_config=_SPARSE_CONFIG,
            on_disk_payload=True,
        )
        await client.create_payload_index(
            collection_name=target, field_name="document_id", field_schema=qmodels.PayloadSchemaType.KEYWORD
        )
        print(f"created '{target}'")

    done, offset = 0, None
    while True:
        points, offset = await client.scroll(
            collection_name=source, limit=batch_size, offset=offset, with_payload=True, with_vectors=True
        )
        if not points:
            break
        present = {
            str(r.id): bool((r.payload or {}).get("has_sparse"))
            for r in await client.retrieve(
                collection_name=target, ids=[p.id for p in points], with_payload=["has_sparse"], with_vectors=False
            )
        }
        fresh = [p for p in points if str(p.id) not in present]
        if fresh:
            await client.upsert(
                collection_name=target,
                points=[qmodels.PointStruct(id=p.id, vector=p.vector, payload=p.payload) for p in fresh],
                wait=True,
            )
        needs_sparse = [p for p in points if not present.get(str(p.id), False)]
        pairs = [(str(p.id), (p.payload or {}).get("text", "")) for p in needs_sparse]
        await attach_sparse_vectors(pairs, batch_size, collection=target)
        done += len(points)
        print(f"  {done}/{total}")
        if offset is None:
            break

    copied = (await client.count(collection_name=target, exact=True)).count
    print(f"done: target has {copied} points (source {total}). Set QDRANT_COLLECTION={target} to use it.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="documents_hybrid")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    asyncio.run(main(args.target, args.batch_size, args.dry_run))
