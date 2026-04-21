"""Add conversation_mode column to threads

Revision ID: add_thread_conversation_mode
Revises: 8538d84e49b6
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa


revision = 'add_thread_conversation_mode'
down_revision = '8538d84e49b6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('threads', sa.Column('conversation_mode', sa.String(30), nullable=True))


def downgrade():
    op.drop_column('threads', 'conversation_mode')
