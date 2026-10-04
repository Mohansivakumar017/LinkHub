"""allow reuse of aliases owned by soft-deleted links

Revision ID: 0011_reuse_deleted_aliases
Revises: 0010_api_key_org_scope
"""

import sqlalchemy as sa

from alembic import op

revision = "0011_reuse_deleted_aliases"
down_revision = "0010_api_key_org_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_urls_short_code", "urls", type_="unique")
    op.drop_constraint("uq_urls_custom_alias", "urls", type_="unique")
    op.drop_index("ix_urls_short_code", table_name="urls")
    op.drop_index("ix_urls_custom_alias", table_name="urls")

    op.create_index(
        "ix_urls_short_code",
        "urls",
        ["short_code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_urls_custom_alias",
        "urls",
        ["custom_alias"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_urls_custom_alias", table_name="urls")
    op.drop_index("ix_urls_short_code", table_name="urls")

    op.create_unique_constraint("uq_urls_short_code", "urls", ["short_code"])
    op.create_unique_constraint("uq_urls_custom_alias", "urls", ["custom_alias"])
    op.create_index("ix_urls_short_code", "urls", ["short_code"], unique=True)
    op.create_index("ix_urls_custom_alias", "urls", ["custom_alias"], unique=True)
