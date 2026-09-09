"""create urls table

Revision ID: 0003_create_urls_table
Revises: 0002_create_organizations_and_memberships
Create Date: 2026-07-29 01:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_create_urls_table"
down_revision = "0002_organizations_memberships"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "urls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("short_code", sa.String(length=64), nullable=False),
        sa.Column("custom_alias", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("one_time", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("click_limit", sa.Integer(), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("short_code"),
        sa.UniqueConstraint("custom_alias"),
    )
    op.create_index("ix_urls_organization_id", "urls", ["organization_id"], unique=False)
    op.create_index("ix_urls_owner_user_id", "urls", ["owner_user_id"], unique=False)
    op.create_index("ix_urls_short_code", "urls", ["short_code"], unique=True)
    op.create_index("ix_urls_custom_alias", "urls", ["custom_alias"], unique=True)


def downgrade():
    op.drop_index("ix_urls_custom_alias", table_name="urls")
    op.drop_index("ix_urls_short_code", table_name="urls")
    op.drop_index("ix_urls_owner_user_id", table_name="urls")
    op.drop_index("ix_urls_organization_id", table_name="urls")
    op.drop_table("urls")
