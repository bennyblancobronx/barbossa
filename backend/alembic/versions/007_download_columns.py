"""Add missing download columns

Revision ID: 007_download_columns
Revises: 006_remove_admin_user
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '007_download_columns'
down_revision: Union[str, None] = '006_remove_admin_user'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add celery_task_id column (only missing column)
    op.add_column('downloads', sa.Column('celery_task_id', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('downloads', 'celery_task_id')
