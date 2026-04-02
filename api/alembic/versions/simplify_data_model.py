"""Simplify data model - OASF-aligned confabs, thread participants, message threading

Revision ID: simplify_data_model
Revises: add_threads_messages
Create Date: 2026-03-25

Changes:
- confabs: Add OASF fields, purpose, guardrails, tests, runtime config, GitHub sync
- confab_learnings: New table for knowledge management
- thread_participants: New table replacing thread_mapping
- threads: Rename thread_name to name
- messages: Add sender info, threading (in_reply_to, depth), addressing
- thread_mapping: Drop (replaced by thread_participants)
"""
from alembic import op
import sqlalchemy as sa


revision = 'simplify_data_model'
down_revision = 'add_threads_messages'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # 1. Alter confabs table - add new fields
    # =========================================================================

    # OASF metadata
    op.add_column('confabs', sa.Column('oasf_schema_version', sa.String(20), nullable=False, server_default='1.0.0'))
    op.add_column('confabs', sa.Column('skills', sa.JSON(), nullable=True))
    op.add_column('confabs', sa.Column('domains', sa.JSON(), nullable=True))

    # Core content
    op.add_column('confabs', sa.Column('purpose', sa.Text(), nullable=True))
    op.add_column('confabs', sa.Column('guardrails', sa.JSON(), nullable=True))
    op.add_column('confabs', sa.Column('tests', sa.JSON(), nullable=True))

    # Runtime config
    op.add_column('confabs', sa.Column('model_provider', sa.String(50), nullable=True, server_default='groq'))
    op.add_column('confabs', sa.Column('model_name', sa.String(100), nullable=True, server_default='qwen/qwen3-32b'))
    op.add_column('confabs', sa.Column('temperature', sa.Float(), nullable=False, server_default='0.7'))

    # Full OASF export
    op.add_column('confabs', sa.Column('oasf_yaml', sa.Text(), nullable=True))

    # GitHub sync state
    op.add_column('confabs', sa.Column('github_path', sa.String(255), nullable=True))
    op.add_column('confabs', sa.Column('github_synced_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('confabs', sa.Column('github_sync_version', sa.String(50), nullable=True))

    # Drop old config column (data migrated to new fields)
    op.drop_column('confabs', 'config')
    # Rename github_url to github_path if data exists (optional, could keep both)
    op.drop_column('confabs', 'github_url')

    # =========================================================================
    # 2. Create confab_learnings table
    # =========================================================================
    op.create_table(
        'confab_learnings',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('confab_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('summary', sa.String(500), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('author_type', sa.String(20), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('source_thread_id', sa.Integer(), nullable=True),
        sa.Column('github_filename', sa.String(255), nullable=True),
        sa.Column('github_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['confab_id'], ['confabs.id'], name='fk_confab_learnings_confab_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_thread_id'], ['threads.id'], name='fk_confab_learnings_source_thread_id'),
    )
    op.create_index('ix_confab_learnings_id', 'confab_learnings', ['id'])
    op.create_index('ix_confab_learnings_confab_id', 'confab_learnings', ['confab_id'])

    # =========================================================================
    # 3. Create thread_participants table
    # =========================================================================
    op.create_table(
        'thread_participants',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('thread_id', sa.Integer(), nullable=False),
        sa.Column('participant_type', sa.String(20), nullable=False),
        sa.Column('participant_id', sa.Integer(), nullable=True),
        sa.Column('system_agent_name', sa.String(100), nullable=True),
        sa.Column('role', sa.String(20), nullable=False, server_default='participant'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('left_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['thread_id'], ['threads.id'], name='fk_thread_participants_thread_id', ondelete='CASCADE'),
    )
    op.create_index('ix_thread_participants_id', 'thread_participants', ['id'])
    op.create_index('ix_thread_participants_thread_id', 'thread_participants', ['thread_id'])

    # =========================================================================
    # 4. Alter threads table - rename thread_name to name
    # =========================================================================
    op.alter_column('threads', 'thread_name', new_column_name='name')

    # =========================================================================
    # 5. Alter messages table - add sender info, threading, addressing
    # =========================================================================

    # Sender info
    op.add_column('messages', sa.Column('sender_type', sa.String(20), nullable=False, server_default='user'))
    op.add_column('messages', sa.Column('sender_id', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('sender_name', sa.String(255), nullable=True))

    # Threading
    op.add_column('messages', sa.Column('in_reply_to', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('depth', sa.Integer(), nullable=False, server_default='0'))

    # Addressing
    op.add_column('messages', sa.Column('addressed_to', sa.JSON(), nullable=True))

    # Rename time to created_at
    op.alter_column('messages', 'time', new_column_name='created_at')

    # Add self-referential FK for in_reply_to
    op.create_foreign_key(
        'fk_messages_in_reply_to',
        'messages', 'messages',
        ['in_reply_to'], ['id']
    )

    # =========================================================================
    # 6. Drop thread_mapping table (if exists)
    # =========================================================================
    # Check if thread_mapping exists before dropping
    op.execute("""
        DROP TABLE IF EXISTS thread_mapping CASCADE;
    """)


def downgrade() -> None:
    # Recreate thread_mapping
    op.create_table(
        'thread_mapping',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('confab_id', sa.Integer(), nullable=False),
        sa.Column('thread_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['confab_id'], ['confabs.id'], name='fk_thread_mapping_confab_id'),
        sa.ForeignKeyConstraint(['thread_id'], ['threads.id'], name='fk_thread_mapping_thread_id'),
    )

    # Revert messages
    op.drop_constraint('fk_messages_in_reply_to', 'messages', type_='foreignkey')
    op.alter_column('messages', 'created_at', new_column_name='time')
    op.drop_column('messages', 'addressed_to')
    op.drop_column('messages', 'depth')
    op.drop_column('messages', 'in_reply_to')
    op.drop_column('messages', 'sender_name')
    op.drop_column('messages', 'sender_id')
    op.drop_column('messages', 'sender_type')

    # Revert threads
    op.alter_column('threads', 'name', new_column_name='thread_name')

    # Drop thread_participants
    op.drop_index('ix_thread_participants_thread_id', table_name='thread_participants')
    op.drop_index('ix_thread_participants_id', table_name='thread_participants')
    op.drop_table('thread_participants')

    # Drop confab_learnings
    op.drop_index('ix_confab_learnings_confab_id', table_name='confab_learnings')
    op.drop_index('ix_confab_learnings_id', table_name='confab_learnings')
    op.drop_table('confab_learnings')

    # Revert confabs
    op.add_column('confabs', sa.Column('github_url', sa.String(500), nullable=True))
    op.add_column('confabs', sa.Column('config', sa.JSON(), nullable=True))
    op.drop_column('confabs', 'github_sync_version')
    op.drop_column('confabs', 'github_synced_at')
    op.drop_column('confabs', 'github_path')
    op.drop_column('confabs', 'oasf_yaml')
    op.drop_column('confabs', 'temperature')
    op.drop_column('confabs', 'model_name')
    op.drop_column('confabs', 'model_provider')
    op.drop_column('confabs', 'tests')
    op.drop_column('confabs', 'guardrails')
    op.drop_column('confabs', 'purpose')
    op.drop_column('confabs', 'domains')
    op.drop_column('confabs', 'skills')
    op.drop_column('confabs', 'oasf_schema_version')
