"""Add album metadata columns: upc, release_type

Revision ID: 016_add_album_metadata
Revises: 015_add_artist_metadata
Create Date: 2026-01-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '016_add_album_metadata'
down_revision: Union[str, None] = '015_add_artist_metadata'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # UPC: Universal Product Code / barcode (12-13 digits)
    op.add_column('albums', sa.Column('upc', sa.String(13)))

    # Release type: album, single, ep, compilation, soundtrack, live, remix
    op.add_column('albums', sa.Column('release_type', sa.String(20)))

    # Add index on UPC for lookups
    op.create_index('ix_albums_upc', 'albums', ['upc'])


def downgrade() -> None:
    op.drop_index('ix_albums_upc', 'albums')
    op.drop_column('albums', 'release_type')
    op.drop_column('albums', 'upc')
