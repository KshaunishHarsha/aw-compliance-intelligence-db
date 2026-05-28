"""add fts_vector to documents with trigger and GIN index

Revision ID: f7b8c9d0e1f2
Revises: e6a7b8c9d0e1
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "f7b8c9d0e1f2"
down_revision = "e6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add fts_vector column
    op.add_column("documents", sa.Column("fts_vector", TSVECTOR, nullable=True))

    # Trigger function: retrieval_summary → weight A, raw_text → weight B
    op.execute("""
        CREATE OR REPLACE FUNCTION documents_fts_update() RETURNS trigger AS $$
        BEGIN
          NEW.fts_vector :=
            setweight(to_tsvector('english', coalesce(NEW.retrieval_summary, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(LEFT(NEW.raw_text, 500000), '')), 'B');
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_documents_fts_update
        BEFORE INSERT OR UPDATE OF retrieval_summary, raw_text
        ON documents
        FOR EACH ROW EXECUTE FUNCTION documents_fts_update();
    """)

    # GIN index for fast full-text search
    op.execute("""
        CREATE INDEX idx_documents_fts ON documents USING gin(fts_vector);
    """)

    # Backfill existing rows
    op.execute("""
        UPDATE documents SET retrieval_summary = retrieval_summary;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_documents_fts")
    op.execute("DROP TRIGGER IF EXISTS trg_documents_fts_update ON documents")
    op.execute("DROP FUNCTION IF EXISTS documents_fts_update()")
    op.drop_column("documents", "fts_vector")
