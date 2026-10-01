"""Schemas for user collections (groups of documents), not Qdrant collections."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

CollectionName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class CollectionCreate(BaseModel):
    name: CollectionName


class CollectionOut(BaseModel):
    id: uuid.UUID
    name: str
    document_count: int
    created_at: datetime


class CollectionListResponse(BaseModel):
    total: int
    collections: list[CollectionOut]


class CollectionDeleteResponse(BaseModel):
    id: uuid.UUID
    name: str
    documents_released: int
    message: str = "Collection deleted. Its documents are still in your library."


class AssignRequest(BaseModel):
    collection_id: uuid.UUID | None = None


class AssignResponse(BaseModel):
    document_id: uuid.UUID
    collection_id: uuid.UUID | None
