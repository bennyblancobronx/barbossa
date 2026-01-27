"""Add unique constraint to prevent duplicate albums

Revision ID: 012_album_unique_constraint
Revises: 011_user_artists
Create Date: 2026-01-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '012_album_unique_constraint'
down_revision: Union[str, None] = '011_user_artists'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unique constraint on artist_id + normalized_title
    op.create_unique_constraint(
        'uq_album_artist_title',
        'albums',
        ['artist_id', 'normalized_title']
    )


def downgrade() -> None:
    op.drop_constraint('uq_album_artist_title', 'albums', type_='unique')
