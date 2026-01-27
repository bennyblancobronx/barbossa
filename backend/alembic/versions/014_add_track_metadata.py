"""Add track metadata columns: isrc, composer, explicit

Revision ID: 014_add_track_metadata
Revises: 013_track_unique_constraint
Create Date: 2026-01-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '014_add_track_metadata'
down_revision: Union[str, None] = '013_track_unique_constraint'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ISRC: International Standard Recording Code (12 characters, no hyphens)
    op.add_column('tracks', sa.Column('isrc', sa.String(12)))

    # Composer: Important for classical music
    op.add_column('tracks', sa.Column('composer', sa.String(255)))

    # Explicit: Parental advisory flag
    op.add_column('tracks', sa.Column('explicit', sa.Boolean(), server_default='false'))

    # Add index on ISRC for lookups
    op.create_index('ix_tracks_isrc', 'tracks', ['isrc'])


def downgrade() -> None:
    op.drop_index('ix_tracks_isrc', 'tracks')
    op.drop_column('tracks', 'explicit')
    op.drop_column('tracks', 'composer')
    op.drop_column('tracks', 'isrc')
