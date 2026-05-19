"""Add confab RAG dashboard fields

Revision ID: add_confab_rag_dashboard_fields
Revises: add_confab_dashboard_fields
Create Date: 2026-05-19
"""

from alembic import op
import sqlalchemy as sa


revision = "add_confab_rag_dashboard_fields"
down_revision = "add_confab_dashboard_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "confab_deployments",
        sa.Column("rag_dashboard_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("confab_deployments", sa.Column("rag_dashboard_port", sa.Integer(), nullable=True))
    op.add_column("confab_deployments", sa.Column("rag_dashboard_url_external", sa.Text(), nullable=True))
    op.add_column("confab_deployments", sa.Column("rag_dashboard_url_internal", sa.Text(), nullable=True))
    op.add_column("confab_deployments", sa.Column("rag_dashboard_container_name", sa.String(255), nullable=True))
    op.add_column("confab_deployments", sa.Column("rag_dashboard_api_key_hash", sa.String(255), nullable=True))
    op.add_column("confab_deployments", sa.Column("lightrag_workspace", sa.String(255), nullable=True))
    op.create_index(
        "ix_confab_deployments_rag_dashboard_port",
        "confab_deployments",
        ["rag_dashboard_port"],
        unique=True,
    )
    op.create_index(
        "ix_confab_deployments_rag_dashboard_container_name",
        "confab_deployments",
        ["rag_dashboard_container_name"],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_confab_deployments_rag_dashboard_container_name", table_name="confab_deployments")
    op.drop_index("ix_confab_deployments_rag_dashboard_port", table_name="confab_deployments")
    op.drop_column("confab_deployments", "lightrag_workspace")
    op.drop_column("confab_deployments", "rag_dashboard_api_key_hash")
    op.drop_column("confab_deployments", "rag_dashboard_container_name")
    op.drop_column("confab_deployments", "rag_dashboard_url_internal")
    op.drop_column("confab_deployments", "rag_dashboard_url_external")
    op.drop_column("confab_deployments", "rag_dashboard_port")
    op.drop_column("confab_deployments", "rag_dashboard_enabled")
