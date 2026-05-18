"""Add confab deployments

Revision ID: add_confab_deployments
Revises: add_thread_conversation_mode
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "add_confab_deployments"
down_revision = "add_thread_conversation_mode"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "confab_deployments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("confab_id", sa.Integer(), sa.ForeignKey("confabs.id"), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("runtime", sa.String(50), nullable=False, server_default="hermes_profile"),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("status_detail", sa.Text(), nullable=True),
        sa.Column("profile_name", sa.String(255), nullable=False, unique=True),
        sa.Column("model_id", sa.String(255), nullable=False, unique=True),
        sa.Column("container_name", sa.String(255), nullable=False, unique=True),
        sa.Column("profile_host_path", sa.Text(), nullable=False),
        sa.Column("api_port", sa.Integer(), nullable=False, unique=True),
        sa.Column("api_server_key_hash", sa.String(255), nullable=False),
        sa.Column("api_base_url_external", sa.Text(), nullable=False),
        sa.Column("api_base_url_internal", sa.Text(), nullable=False),
        sa.Column("rag_workspace", sa.String(255), nullable=False),
        sa.Column("rag_prefix", sa.String(255), nullable=False),
        sa.Column("openwebui_model_id", sa.String(255), nullable=True),
        sa.Column("router_registered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_sync_result", sa.JSON(), nullable=True),
        sa.Column("last_health", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("llm_provider", sa.String(100), nullable=True),
        sa.Column("llm_model", sa.String(255), nullable=True),
        sa.Column("llm_config_source", sa.String(50), nullable=False, server_default="platform_default"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_confab_deployments_id", "confab_deployments", ["id"])


def downgrade():
    op.drop_index("ix_confab_deployments_id", table_name="confab_deployments")
    op.drop_table("confab_deployments")
