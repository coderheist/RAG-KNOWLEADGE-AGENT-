"""
User collections (Phase: collections that actually scope retrieval).

A collection lives in PostgreSQL; a document belongs to at most one. The collection id is mirrored into the
payload of every Qdrant point of the document, so a question can be filtered to a collection inside the vector
search (see retrieval_service.collection_filter). Qdrant is updated first and PostgreSQL second, so a vector-store
failure leaves the database untouched and the call can simply be retried.
"""
import uuid

from qdrant_client.http import models as qmodels
from sqlalchemy import delete, func, select, update

from app.config import get_settings
from app.db.library_models import DocumentCollection
from app.db.models import Document
from app.db.postgres import get_db_session
from app.db.qdrant import get_qdrant_client
from app.schemas.library import CollectionOut
from app.utils.logging import get_logger

logger = get_logger(__name__)


class NotFoundError(KeyError):
    """A document or collection does not exist."""


def _match(key: str, value: str) -> qmodels.Filter:
    return qmodels.Filter(must=[qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value))])


async def _set_vector_collection(document_id: str, collection_id: str | None) -> None:
    client = get_qdrant_client()
    name = get_settings().QDRANT_COLLECTION
    selector = _match("document_id", document_id)
    if collection_id:
        await client.set_payload(
            collection_name=name, payload={"collection_id": collection_id}, points=selector, wait=True
        )
    else:
        await client.delete_payload(collection_name=name, keys=["collection_id"], points=selector, wait=True)


async def list_collections() -> list[CollectionOut]:
    async with get_db_session() as session:
        rows = (
            await session.execute(
                select(DocumentCollection, func.count(Document.id))
                .outerjoin(Document, Document.collection_id == DocumentCollection.id)
                .group_by(DocumentCollection.id)
                .order_by(func.lower(DocumentCollection.name))
            )
        ).all()
    return [CollectionOut(id=c.id, name=c.name, document_count=n, created_at=c.created_at) for c, n in rows]


async def collection_exists(collection_id: uuid.UUID) -> bool:
    async with get_db_session() as session:
        found = await session.execute(select(DocumentCollection.id).where(DocumentCollection.id == collection_id))
        return found.first() is not None


async def create_collection(name: str) -> CollectionOut:
    """Create a collection. Raises ValueError when the (case-insensitive) name is empty or already taken."""
    clean = " ".join(name.split())
    if not clean:
        raise ValueError("A collection needs a name.")
    async with get_db_session() as session:
        taken = await session.execute(
            select(DocumentCollection.id).where(func.lower(DocumentCollection.name) == clean.lower())
        )
        if taken.first() is not None:
            raise ValueError(f"A collection named \"{clean}\" already exists.")
        row = DocumentCollection(name=clean)
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return CollectionOut(id=row.id, name=row.name, document_count=0, created_at=row.created_at)


async def delete_collection(collection_id: uuid.UUID) -> tuple[str, int]:
    """Delete a collection and release its documents (they stay indexed). Returns (name, documents released)."""
    async with get_db_session() as session:
        row = (
            await session.execute(select(DocumentCollection).where(DocumentCollection.id == collection_id))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(f"Collection '{collection_id}' not found.")
        name = row.name
        released = (
            await session.execute(
                select(func.count()).select_from(Document).where(Document.collection_id == collection_id)
            )
        ).scalar_one()
    try:
        client = get_qdrant_client()
        await client.delete_payload(
            collection_name=get_settings().QDRANT_COLLECTION,
            keys=["collection_id"],
            points=_match("collection_id", str(collection_id)),
            wait=True,
        )
    except Exception as exc:
        raise RuntimeError(f"Vector store update failed ({exc}). Nothing was deleted; retry.") from exc
    async with get_db_session() as session:
        await session.execute(delete(DocumentCollection).where(DocumentCollection.id == collection_id))
    logger.info("Collection '%s' deleted; %d document(s) released", name, released)
    return name, released


async def assign_document(
    document_id: uuid.UUID, collection_id: uuid.UUID | None, only_if_unassigned: bool = False
) -> bool:
    """Put a document in a collection (or None to release it). Returns False when nothing needed to change."""
    async with get_db_session() as session:
        doc = (await session.execute(select(Document).where(Document.id == document_id))).scalar_one_or_none()
        if doc is None:
            raise NotFoundError(f"Document '{document_id}' not found.")
        if collection_id is not None:
            found = await session.execute(select(DocumentCollection.id).where(DocumentCollection.id == collection_id))
            if found.first() is None:
                raise NotFoundError(f"Collection '{collection_id}' not found.")
        current = doc.collection_id
    if current == collection_id or (only_if_unassigned and current is not None):
        return False
    try:
        await _set_vector_collection(str(document_id), str(collection_id) if collection_id else None)
    except Exception as exc:
        raise RuntimeError(f"Vector store update failed ({exc}). Nothing was changed; retry.") from exc
    async with get_db_session() as session:
        await session.execute(update(Document).where(Document.id == document_id).values(collection_id=collection_id))
    return True
