"""add api key usage count

Revision ID: 0007_add_api_key_usage_count
Revises: 0006_create_api_keys
"""

import sqlalchemy as sa

from alembic import op

revision = "0007_add_api_key_usage_count"
down_revision = "0006_create_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "usage_count")
