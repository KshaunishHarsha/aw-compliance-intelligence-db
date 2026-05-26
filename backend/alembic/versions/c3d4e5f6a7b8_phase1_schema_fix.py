"""Phase 1 schema fix: users table, ingested_by FK, source column, missing indexes

Revision ID: c3d4e5f6a7b8
Revises: bd5f91232614
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'bd5f91232614'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('hashed_password', sa.Text(), nullable=False),
        sa.Column('full_name', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), server_default='user', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('idx_users_email', 'users', ['email'])

    # Add source column to documents
    op.add_column('documents', sa.Column('source', sa.Text(), nullable=True))

    # Rename uploaded_by -> ingested_by
    op.alter_column('documents', 'uploaded_by', new_column_name='ingested_by')

    # Add FK from documents.ingested_by -> users.id
    op.create_foreign_key(
        'fk_documents_ingested_by_users',
        'documents', 'users',
        ['ingested_by'], ['id'],
        ondelete='SET NULL',
    )

    # Fix inspection_date from TIMESTAMP to DATE
    op.alter_column(
        'document_metadata', 'inspection_date',
        existing_type=sa.DateTime(),
        type_=sa.Date(),
        existing_nullable=True,
    )

    # Missing indexes from initial migration
    op.create_index('idx_documents_status', 'documents', ['status'])
    op.create_index('idx_documents_doc_type', 'documents', ['doc_type'])
    op.create_index('idx_documents_source', 'documents', ['source'])
    op.create_index('idx_document_metadata_document_id', 'document_metadata', ['document_id'])
    op.create_index('idx_document_metadata_jurisdiction', 'document_metadata', ['jurisdiction'])
    op.create_index(
        'idx_document_metadata_species', 'document_metadata', ['species'],
        postgresql_using='gin',
    )
    op.create_index(
        'idx_document_metadata_categories', 'document_metadata', ['categories'],
        postgresql_using='gin',
    )


def downgrade() -> None:
    op.drop_index('idx_document_metadata_categories', table_name='document_metadata')
    op.drop_index('idx_document_metadata_species', table_name='document_metadata')
    op.drop_index('idx_document_metadata_jurisdiction', table_name='document_metadata')
    op.drop_index('idx_document_metadata_document_id', table_name='document_metadata')
    op.drop_index('idx_documents_source', table_name='documents')
    op.drop_index('idx_documents_doc_type', table_name='documents')
    op.drop_index('idx_documents_status', table_name='documents')

    op.alter_column(
        'document_metadata', 'inspection_date',
        existing_type=sa.Date(),
        type_=sa.DateTime(),
        existing_nullable=True,
    )

    op.drop_constraint('fk_documents_ingested_by_users', 'documents', type_='foreignkey')
    op.alter_column('documents', 'ingested_by', new_column_name='uploaded_by')
    op.drop_column('documents', 'source')

    op.drop_index('idx_users_email', table_name='users')
    op.drop_table('users')
