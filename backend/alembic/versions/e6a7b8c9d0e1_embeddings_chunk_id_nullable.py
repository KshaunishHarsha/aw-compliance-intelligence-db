"""make embeddings.chunk_id nullable for document-level embeddings

Revision ID: e6a7b8c9d0e1
Revises: d5f6a7b8c9d0
Create Date: 2026-05-27
"""
from alembic import op

revision = "e6a7b8c9d0e1"
down_revision = "d5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("embeddings", "chunk_id", nullable=True)


def downgrade() -> None:
    op.alter_column("embeddings", "chunk_id", nullable=False)
