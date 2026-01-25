"""Add source_url to pending_review

Revision ID: 009_pending_review_source_url
Revises: 008_pending_review
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '009_pending_review_source_url'
down_revision: Union[str, None] = '008_pending_review'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pending_review', sa.Column('source_url', sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column('pending_review', 'source_url')
