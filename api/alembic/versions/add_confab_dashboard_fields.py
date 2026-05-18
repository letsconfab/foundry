"""Add confab dashboard fields

Revision ID: add_confab_dashboard_fields
Revises: add_confab_deployments
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa


revision = "add_confab_dashboard_fields"
down_revision = "add_confab_deployments"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "confab_deployments",
        sa.Column("dashboard_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("confab_deployments", sa.Column("dashboard_port", sa.Integer(), nullable=True))
    op.add_column("confab_deployments", sa.Column("dashboard_url_external", sa.Text(), nullable=True))
    op.add_column("confab_deployments", sa.Column("dashboard_url_internal", sa.Text(), nullable=True))
    op.create_index(
        "ix_confab_deployments_dashboard_port",
        "confab_deployments",
        ["dashboard_port"],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_confab_deployments_dashboard_port", table_name="confab_deployments")
    op.drop_column("confab_deployments", "dashboard_url_internal")
    op.drop_column("confab_deployments", "dashboard_url_external")
    op.drop_column("confab_deployments", "dashboard_port")
    op.drop_column("confab_deployments", "dashboard_enabled")
