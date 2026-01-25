"""Add pending review support

Revision ID: 008_pending_review
Revises: 007_download_columns
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '008_pending_review'
down_revision: Union[str, None] = '007_download_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add result_review_id column for linking downloads to pending reviews
    op.add_column('downloads', sa.Column('result_review_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_downloads_result_review_id',
        'downloads', 'pending_reviews',
        ['result_review_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_downloads_result_review_id', 'downloads', type_='foreignkey')
    op.drop_column('downloads', 'result_review_id')
