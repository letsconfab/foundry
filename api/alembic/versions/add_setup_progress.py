"""Add setup_progress field to confabs for Foreman tracking

Revision ID: add_setup_progress
Revises: simplify_data_model
Create Date: 2026-03-25

Adds a JSON field to track Foreman setup progress:
- completed_steps: list of step numbers (1-7)
- current_stage: current stage name (purpose, participants, etc.)
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_setup_progress'
down_revision = 'simplify_data_model'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('confabs', sa.Column('setup_progress', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('confabs', 'setup_progress')
