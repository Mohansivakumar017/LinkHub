"""allow pending organization invitations to be revoked

Revision ID: 0014_revoke_org_invites
Revises: 0013_user_auth_version
"""

import sqlalchemy as sa

from alembic import op

revision = "0014_revoke_org_invites"
down_revision = "0013_user_auth_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organization_invites",
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organization_invites", "revoked_at")
