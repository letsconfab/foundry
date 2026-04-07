"""Remove V1 document store tables

Revision ID: 8538d84e49b6
Revises: f7c272bd94a9
Create Date: 2026-04-07 17:31:29.339434

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8538d84e49b6'
down_revision = 'f7c272bd94a9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop V1 document store tables (confab_documents and document_chunks).

    V1 document store used chunking and ChromaDB embeddings.
    V2 document store (confab_documents_v2, document_versions) replaces it
    with versioned compressed storage.
    """
    # Drop document_chunks first (has FK to confab_documents)
    op.drop_index(op.f('ix_document_chunks_id'), table_name='document_chunks')
    op.drop_table('document_chunks')

    # Drop confab_documents
    op.drop_index(op.f('ix_confab_documents_id'), table_name='confab_documents')
    op.drop_table('confab_documents')


def downgrade() -> None:
    """Recreate V1 document store tables.

    WARNING: This only recreates the schema. Data is not recoverable.
    """
    # Recreate confab_documents first (parent table)
    op.create_table('confab_documents',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('confab_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('filename', sa.VARCHAR(length=500), autoincrement=False, nullable=False),
        sa.Column('content_type', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column('source', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
        sa.Column('source_url', sa.VARCHAR(length=2000), autoincrement=False, nullable=True),
        sa.Column('content_hash', sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column('raw_content', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('file_path', sa.VARCHAR(length=500), autoincrement=False, nullable=True),
        sa.Column('chunk_count', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('status', sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column('error_message', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('metadata_json', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['confab_id'], ['confabs.id'], name=op.f('confab_documents_confab_id_fkey')),
        sa.PrimaryKeyConstraint('id', name=op.f('confab_documents_pkey'))
    )
    op.create_index(op.f('ix_confab_documents_id'), 'confab_documents', ['id'], unique=False)

    # Recreate document_chunks (child table)
    op.create_table('document_chunks',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('chunk_index', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('content', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('start_char', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('end_char', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('vector_id', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['confab_documents.id'], name=op.f('document_chunks_document_id_fkey')),
        sa.PrimaryKeyConstraint('id', name=op.f('document_chunks_pkey'))
    )
    op.create_index(op.f('ix_document_chunks_id'), 'document_chunks', ['id'], unique=False)
