"""Remove admin user concept

Revision ID: 006_remove_admin_user
Revises: 005
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '006_remove_admin_user'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove is_admin column from users table
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("users")]
    if "is_admin" in columns:
        op.drop_column('users', 'is_admin')


def downgrade() -> None:
    # Re-add is_admin column
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), server_default='false'))
