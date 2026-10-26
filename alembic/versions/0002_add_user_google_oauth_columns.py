"""add user google oauth columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26 10:30:00.000000+00:00

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "auth_provider", sa.String(), nullable=False, server_default="local"
        ),
    )
    op.add_column("user", sa.Column("google_sub", sa.String(), nullable=True))
    op.create_index(op.f("ix_user_google_sub"), "user", ["google_sub"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_google_sub"), table_name="user")
    op.drop_column("user", "google_sub")
    op.drop_column("user", "auth_provider")
