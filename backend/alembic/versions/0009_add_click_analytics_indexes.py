"""add click analytics indexes

Revision ID: 0009_click_indexes
Revises: 0008_expiration_marker
"""

from alembic import op

revision = "0009_click_indexes"
down_revision = "0008_expiration_marker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_clicks_organization_created_at",
        "clicks",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_clicks_url_created_at",
        "clicks",
        ["url_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_clicks_url_created_at", table_name="clicks")
    op.drop_index("ix_clicks_organization_created_at", table_name="clicks")
