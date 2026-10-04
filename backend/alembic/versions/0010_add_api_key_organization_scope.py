"""add optional organization scope to api keys

Revision ID: 0010_add_api_key_organization_scope
Revises: 0009_add_click_analytics_indexes
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_api_key_org_scope"
down_revision = "0009_click_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_api_keys_organization_id",
        "api_keys",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_api_keys_organization_id",
        "api_keys",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_api_keys_organization_id", table_name="api_keys")
    op.drop_constraint(
        "fk_api_keys_organization_id", "api_keys", type_="foreignkey"
    )
    op.drop_column("api_keys", "organization_id")
