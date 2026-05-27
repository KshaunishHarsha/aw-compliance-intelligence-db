"""add parent_document_id to documents

Revision ID: d5f6a7b8c9d0
Revises: c3d4e5f6a7b8
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "d5f6a7b8c9d0"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "parent_document_id",
            sa.UUID(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("idx_documents_parent_id", "documents", ["parent_document_id"])


def downgrade() -> None:
    op.drop_index("idx_documents_parent_id", table_name="documents")
    op.drop_column("documents", "parent_document_id")
