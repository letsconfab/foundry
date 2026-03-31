"""add threads and messages tables

Revision ID: add_threads_messages
Revises: 6505d14a7ba4
Create Date: 2025-02-17

Tables: users (existing), threads (thread_id/id, thread_name, createdAt, owner_user_id),
       messages (id, thread_id, content, time)
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_threads_messages'
down_revision = '6505d14a7ba4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'threads',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('thread_name', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('owner_user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], name='fk_threads_owner_user_id_users'),
    )
    op.create_index('ix_threads_id', 'threads', ['id'])
    op.create_index('ix_threads_owner_user_id', 'threads', ['owner_user_id'])

    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('thread_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('time', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['thread_id'], ['threads.id'], name='fk_messages_thread_id_threads'),
    )
    op.create_index('ix_messages_id', 'messages', ['id'])
    op.create_index('ix_messages_thread_id', 'messages', ['thread_id'])


def downgrade() -> None:
    op.drop_index('ix_messages_thread_id', table_name='messages')
    op.drop_index('ix_messages_id', table_name='messages')
    op.drop_table('messages')
    op.drop_index('ix_threads_owner_user_id', table_name='threads')
    op.drop_index('ix_threads_id', table_name='threads')
    op.drop_table('threads')
