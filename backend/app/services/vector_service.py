"""
Qdrant vector store operations.

Responsibilities:
  - Ensure the collection exists with the correct vector configuration.
  - Upsert document chunk vectors with rich payload for retrieval.
  - Provide a clean delete-by-document-id helper for future use.
"""

import uuid
from dataclasses import dataclass

from qdrant_client.http import models as qmodels

from app.config import get_settings
from app.db.qdrant import get_qdrant_client
from app.services import sparse
from app.services.sparse import SPARSE_VECTOR_NAME
from app.utils.logging import get_logger

logger = get_logger(__name__)

# IDF is applied by Qdrant at query time; fastembed's BM25 emits term-frequency weights only.
_SPARSE_CONFIG = {SPARSE_VECTOR_NAME: qmodels.SparseVectorParams(modifier=qmodels.Modifier.IDF)}

NAMESPACE_RAG = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

def generate_point_id(
    filename: str, page_number: int, section: str | None, heading: str | None, chunk_index: int, text: str
) -> str:
    """Generate a deterministic UUID for a chunk based on its content and metadata."""
    stable_name = f"{filename}::{page_number}::{section}::{heading}::{chunk_index}::{text}"
    return str(uuid.uuid5(NAMESPACE_RAG, stable_name))



@dataclass
class VectorPoint:
    """A single vector + payload to be upserted into Qdrant."""

    vector: list[float]
    document_id: str           # UUID string of the parent Document row
    filename: str
    chunk_index: int
    page_number: int
    text: str
    heading: str | None = None
    section: str | None = None


async def ensure_collection() -> None:
    """
    Create the Qdrant collection if it does not already exist.
    Safe to call on every startup — idempotent.
    """
    settings = get_settings()
    client = get_qdrant_client()
    collection_name = settings.QDRANT_COLLECTION

    existing = await client.get_collections()
    names = {c.name for c in existing.collections}

    if collection_name in names:
        logger.debug("Qdrant collection '%s' already exists", collection_name)
        info = await client.get_collection(collection_name)
        if SPARSE_VECTOR_NAME not in (info.config.params.sparse_vectors or {}):
            # Qdrant cannot add a new vector name to an existing collection, so hybrid search needs a migration.
            logger.warning(
                "Collection '%s' has no '%s' sparse vector: dense search works, hybrid search is unavailable. "
                "Run scripts/reindex_hybrid.py and point QDRANT_COLLECTION at the new collection.",
                collection_name, SPARSE_VECTOR_NAME,
            )
        return

    await client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(
            size=settings.EMBEDDING_DIMENSION,
            distance=qmodels.Distance.COSINE,
        ),
        # BM25 sparse vector for hybrid search (Phase 3); harmless while unused
        sparse_vectors_config=_SPARSE_CONFIG,
        # Optimiser settings tuned for read-heavy RAG workloads
        optimizers_config=qmodels.OptimizersConfigDiff(
            indexing_threshold=20_000,
        ),
        # Payload index for fast filtered retrieval by document_id
        on_disk_payload=True,
    )

    # Create a payload index on document_id for fast per-document filtering
    await client.create_payload_index(
        collection_name=collection_name,
        field_name="document_id",
        field_schema=qmodels.PayloadSchemaType.KEYWORD,
    )

    logger.info(
        "Created Qdrant collection '%s' (dim=%d, distance=COSINE)",
        collection_name,
        settings.EMBEDDING_DIMENSION,
    )


async def upsert_vectors(points: list[VectorPoint]) -> int:
    """
    Upsert a batch of vectors into the Qdrant collection.

    Each point receives a random UUID as its Qdrant point ID.
    The ``document_id`` field in the payload is the PostgreSQL row UUID
    and is the join key for cross-store lookups.

    Returns:
        Number of points upserted.
    """
    if not points:
        return 0

    settings = get_settings()
    client = get_qdrant_client()

    qdrant_points = []

    for p in points:
        deterministic_id = generate_point_id(
            p.filename, p.page_number, p.section, p.heading, p.chunk_index, p.text
        )

        qdrant_points.append(
            qmodels.PointStruct(
                id=deterministic_id,
                vector=p.vector,
                payload={
                    "document_id": p.document_id,
                    "filename": p.filename,
                    "chunk_index": p.chunk_index,
                    "page_number": p.page_number,
                    "text": p.text,
                    "char_count": len(p.text),
                    "heading": p.heading,
                    "section": p.section,
                },
            )
        )

    await client.upsert(
        collection_name=settings.QDRANT_COLLECTION,
        points=qdrant_points,
        wait=True,          # wait for WAL flush — guarantees durability
    )

    if settings.ENABLE_HYBRID_SEARCH:
        await attach_sparse_vectors([(str(qp.id), p.text) for qp, p in zip(qdrant_points, points, strict=True)])

    logger.info(
        "Upserted %d vectors into '%s'",
        len(qdrant_points),
        settings.QDRANT_COLLECTION,
    )
    return len(qdrant_points)


async def attach_sparse_vectors(
    id_text_pairs: list[tuple[str, str]], batch_size: int = 64, collection: str | None = None
) -> int:
    """
    Compute BM25 sparse vectors locally and attach them to existing points, leaving the dense vector
    and payload untouched. Used at ingest time and by scripts/reindex_hybrid.py (no re-embedding).
    """
    if not id_text_pairs:
        return 0
    client = get_qdrant_client()
    coll = collection or get_settings().QDRANT_COLLECTION
    for start in range(0, len(id_text_pairs), batch_size):
        batch = id_text_pairs[start : start + batch_size]
        vectors = await sparse.embed_documents([text for _, text in batch])
        ids = [pid for pid, _ in batch]
        await client.update_vectors(
            collection_name=coll,
            points=[
                qmodels.PointVectors(id=pid, vector={SPARSE_VECTOR_NAME: vec})
                for pid, vec in zip(ids, vectors, strict=True)
            ],
            wait=True,
        )
        await client.set_payload(collection_name=coll, payload={"has_sparse": True}, points=ids, wait=True)
    return len(id_text_pairs)


async def delete_by_document_id(document_id: str) -> None:
    """
    Remove all vectors whose payload.document_id matches the given UUID.
    Useful for re-processing or deleting a document.
    """
    settings = get_settings()
    client = get_qdrant_client()

    await client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=document_id),
                    )
                ]
            )
        ),
    )
    logger.info("Deleted vectors for document_id=%s", document_id)


async def get_existing_point_ids(point_ids: list[str]) -> set[str]:
    """
    Given a list of Qdrant point IDs, returns a set of the ones that already exist
    in the collection. Useful for idempotent resumes to avoid re-embedding.
    """
    if not point_ids:
        return set()

    settings = get_settings()
    client = get_qdrant_client()

    # retrieve only the IDs without payload/vectors to be fast
    response = await client.retrieve(
        collection_name=settings.QDRANT_COLLECTION,
        ids=point_ids,
        with_payload=False,
        with_vectors=False
    )
    
    return {str(point.id) for point in response}

