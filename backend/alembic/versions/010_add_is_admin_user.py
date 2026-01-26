"""Add is_admin to users

Revision ID: 010_add_is_admin_user
Revises: 009_pending_review_source_url
Create Date: 2026-01-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010_add_is_admin_user"
down_revision: Union[str, None] = "009_pending_review_source_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin")
