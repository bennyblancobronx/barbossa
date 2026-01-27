"""Add user_artists table for persistent artist hearts

Revision ID: 011_user_artists
Revises: 010_add_is_admin_user
Create Date: 2026-01-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '011_user_artists'
down_revision: Union[str, None] = '010_add_is_admin_user'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_artists',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('artist_id', sa.Integer(), nullable=False),
        sa.Column('auto_add_new', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['artist_id'], ['artists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'artist_id')
    )
    op.create_index('ix_user_artists_artist_id', 'user_artists', ['artist_id'])


def downgrade() -> None:
    op.drop_index('ix_user_artists_artist_id', table_name='user_artists')
    op.drop_table('user_artists')
