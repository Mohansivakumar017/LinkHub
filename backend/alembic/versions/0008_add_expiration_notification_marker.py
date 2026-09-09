"""add expiration notification marker

Revision ID: 0008_expiration_marker
Revises: 0007_add_api_key_usage_count
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_expiration_marker"
down_revision = "0007_add_api_key_usage_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "urls",
        sa.Column("expiration_notified_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("urls", "expiration_notified_at")
