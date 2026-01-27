"""Add artist metadata columns: biography, country

Revision ID: 015_add_artist_metadata
Revises: 014_add_track_metadata
Create Date: 2026-01-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '015_add_artist_metadata'
down_revision: Union[str, None] = '014_add_track_metadata'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Biography: Artist bio from Qobuz or other sources
    op.add_column('artists', sa.Column('biography', sa.Text()))

    # Country: ISO 3166-1 alpha-2 code (e.g., "US", "GB", "DE")
    op.add_column('artists', sa.Column('country', sa.String(2)))


def downgrade() -> None:
    op.drop_column('artists', 'country')
    op.drop_column('artists', 'biography')
