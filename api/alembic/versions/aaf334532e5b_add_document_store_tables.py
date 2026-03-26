"""Add document store tables

Revision ID: aaf334532e5b
Revises: add_setup_progress
Create Date: 2026-03-26 18:15:56.828833

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aaf334532e5b'
down_revision = 'add_setup_progress'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create confab_documents table
    op.create_table(
        'confab_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('confab_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='upload'),
        sa.Column('source_url', sa.String(length=2000), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('raw_content', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['confab_id'], ['confabs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_confab_documents_id'), 'confab_documents', ['id'], unique=False)
    op.create_index(op.f('ix_confab_documents_confab_id'), 'confab_documents', ['confab_id'], unique=False)

    # Create document_chunks table
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('start_char', sa.Integer(), nullable=True),
        sa.Column('end_char', sa.Integer(), nullable=True),
        sa.Column('vector_id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['confab_documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_chunks_id'), 'document_chunks', ['id'], unique=False)
    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_document_chunks_document_id'), table_name='document_chunks')
    op.drop_index(op.f('ix_document_chunks_id'), table_name='document_chunks')
    op.drop_table('document_chunks')
    op.drop_index(op.f('ix_confab_documents_confab_id'), table_name='confab_documents')
    op.drop_index(op.f('ix_confab_documents_id'), table_name='confab_documents')
    op.drop_table('confab_documents')
