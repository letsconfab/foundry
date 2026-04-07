"""Add versioned document store v2

Revision ID: f7c272bd94a9
Revises: aaf334532e5b
Create Date: 2026-04-06 22:41:04.132359

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f7c272bd94a9'
down_revision = 'aaf334532e5b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create confab_documents_v2 table (versioned document metadata)
    op.create_table(
        'confab_documents_v2',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('confab_id', sa.Integer(), nullable=False),
        sa.Column('document_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_content_type', sa.String(length=100), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='upload'),
        sa.Column('source_url', sa.String(length=2000), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['confab_id'], ['confabs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_confab_documents_v2_id'), 'confab_documents_v2', ['id'], unique=False)
    op.create_index(op.f('ix_confab_documents_v2_confab_id'), 'confab_documents_v2', ['confab_id'], unique=False)
    op.create_index(
        'ix_confab_documents_v2_confab_uuid',
        'confab_documents_v2',
        ['confab_id', 'document_uuid'],
        unique=True
    )

    # Create document_versions table (immutable version records)
    op.create_table(
        'document_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        # Content storage
        sa.Column('content_blob', sa.LargeBinary(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('original_size', sa.Integer(), nullable=False),
        sa.Column('compressed_size', sa.Integer(), nullable=False),
        # Encryption metadata (nullable for Phase 1)
        sa.Column('encryption_key_id', sa.String(length=64), nullable=True),
        sa.Column('encryption_iv', sa.LargeBinary(), nullable=True),
        sa.Column('encryption_tag', sa.LargeBinary(), nullable=True),
        # Extracted text
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('text_extraction_status', sa.String(length=20), server_default='pending', nullable=True),
        # Metadata
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        # Timestamps and audit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['confab_documents_v2.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_versions_id'), 'document_versions', ['id'], unique=False)
    op.create_index(op.f('ix_document_versions_document_id'), 'document_versions', ['document_id'], unique=False)
    op.create_index(
        'ix_document_versions_doc_version',
        'document_versions',
        ['document_id', 'version_number'],
        unique=True
    )


def downgrade() -> None:
    # Drop document_versions table
    op.drop_index('ix_document_versions_doc_version', table_name='document_versions')
    op.drop_index(op.f('ix_document_versions_document_id'), table_name='document_versions')
    op.drop_index(op.f('ix_document_versions_id'), table_name='document_versions')
    op.drop_table('document_versions')

    # Drop confab_documents_v2 table
    op.drop_index('ix_confab_documents_v2_confab_uuid', table_name='confab_documents_v2')
    op.drop_index(op.f('ix_confab_documents_v2_confab_id'), table_name='confab_documents_v2')
    op.drop_index(op.f('ix_confab_documents_v2_id'), table_name='confab_documents_v2')
    op.drop_table('confab_documents_v2')
