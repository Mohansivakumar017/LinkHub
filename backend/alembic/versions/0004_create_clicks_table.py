"""create clicks table

Revision ID: 0004_create_clicks_table
Revises: 0003_create_urls_table
Create Date: 2026-08-04 14:20:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_create_clicks_table"
down_revision = "0003_create_urls_table"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "clicks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visitor_key", sa.String(length=64), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("referrer", sa.String(length=1024), nullable=True),
        sa.Column("browser", sa.String(length=128), nullable=True),
        sa.Column("os", sa.String(length=128), nullable=True),
        sa.Column("device", sa.String(length=128), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("city", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["url_id"], ["urls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clicks_url_id", "clicks", ["url_id"], unique=False)
    op.create_index("ix_clicks_organization_id", "clicks", ["organization_id"], unique=False)
    op.create_index("ix_clicks_visitor_key", "clicks", ["visitor_key"], unique=False)
    op.create_index("ix_clicks_created_at", "clicks", ["created_at"], unique=False)


def downgrade():
    op.drop_index("ix_clicks_created_at", table_name="clicks")
    op.drop_index("ix_clicks_visitor_key", table_name="clicks")
    op.drop_index("ix_clicks_organization_id", table_name="clicks")
    op.drop_index("ix_clicks_url_id", table_name="clicks")
    op.drop_table("clicks")
