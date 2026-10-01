"""add user collections

Revision ID: c7e1a9d4b2f0
Revises: b35f99144db8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7e1a9d4b2f0"
down_revision: Union[str, None] = "b35f99144db8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("uq_document_collections_name_lower", "document_collections", [sa.text("lower(name)")], unique=True)
    op.add_column(
        "documents",
        sa.Column(
            "collection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_collections.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_documents_collection_id", "documents", ["collection_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_collection_id", table_name="documents")
    op.drop_column("documents", "collection_id")
    op.drop_index("uq_document_collections_name_lower", table_name="document_collections")
    op.drop_table("document_collections")
