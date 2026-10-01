"""User collections: named groups of documents that a question can be scoped to."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.postgres import Base


class DocumentCollection(Base):
    __tablename__ = "document_collections"
    __table_args__ = (
        # Names are unique regardless of case: "Contracts" and "contracts" are the same collection.
        Index("uq_document_collections_name_lower", text("lower(name)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
