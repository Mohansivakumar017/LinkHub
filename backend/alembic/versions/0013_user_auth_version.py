"""invalidate outstanding access tokens after credential changes

Revision ID: 0013_user_auth_version
Revises: 0012_password_reset_tokens
"""

import sqlalchemy as sa

from alembic import op

revision = "0013_user_auth_version"
down_revision = "0012_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "auth_version",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "auth_version")
