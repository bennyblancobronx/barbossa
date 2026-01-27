"""Add unique constraint to prevent duplicate tracks

Revision ID: 013_track_unique_constraint
Revises: 012_album_unique_constraint
Create Date: 2026-01-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '013_track_unique_constraint'
down_revision: Union[str, None] = '012_album_unique_constraint'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unique constraint on album_id + disc_number + track_number
    # This prevents duplicate track entries for the same position
    op.create_unique_constraint(
        'uq_track_album_position',
        'tracks',
        ['album_id', 'disc_number', 'track_number']
    )


def downgrade() -> None:
    op.drop_constraint('uq_track_album_position', 'tracks', type_='unique')
