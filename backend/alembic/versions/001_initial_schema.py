"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('is_admin', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    # Artists table
    op.create_table(
        'artists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('normalized_name', sa.String(255), nullable=False),
        sa.Column('sort_name', sa.String(255)),
        sa.Column('path', sa.String(1000)),
        sa.Column('artwork_path', sa.String(1000)),
        sa.Column('musicbrainz_id', sa.String(36)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_artists_id', 'artists', ['id'])
    op.create_index('ix_artists_name', 'artists', ['name'])
    op.create_index('ix_artists_normalized_name', 'artists', ['normalized_name'])
    op.create_index('ix_artists_sort_name', 'artists', ['sort_name'])

    # Albums table
    op.create_table(
        'albums',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('artist_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('normalized_title', sa.String(255), nullable=False),
        sa.Column('year', sa.Integer()),
        sa.Column('path', sa.String(1000)),
        sa.Column('artwork_path', sa.String(1000)),
        sa.Column('total_tracks', sa.Integer(), default=0),
        sa.Column('available_tracks', sa.Integer(), default=0),
        sa.Column('disc_count', sa.Integer(), default=1),
        sa.Column('genre', sa.String(100)),
        sa.Column('label', sa.String(255)),
        sa.Column('source', sa.String(50)),
        sa.Column('source_url', sa.String(1000)),
        sa.Column('is_compilation', sa.Boolean(), default=False),
        sa.Column('catalog_number', sa.String(100)),
        sa.Column('musicbrainz_id', sa.String(36)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['artist_id'], ['artists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_albums_id', 'albums', ['id'])
    op.create_index('ix_albums_source', 'albums', ['source'])
    op.create_index('ix_albums_year', 'albums', ['year'])
    op.create_index('ix_albums_title', 'albums', ['title'])
    op.create_index('ix_albums_normalized_title', 'albums', ['normalized_title'])
    op.create_index('ix_albums_artist_id', 'albums', ['artist_id'])

    # Tracks table
    op.create_table(
        'tracks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('album_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('normalized_title', sa.String(255), nullable=False),
        sa.Column('track_number', sa.Integer(), nullable=False),
        sa.Column('disc_number', sa.Integer(), default=1),
        sa.Column('duration', sa.Integer()),
        sa.Column('path', sa.String(1000), nullable=False),
        sa.Column('sample_rate', sa.Integer()),
        sa.Column('bit_depth', sa.Integer()),
        sa.Column('bitrate', sa.Integer()),
        sa.Column('channels', sa.Integer(), default=2),
        sa.Column('file_size', sa.BigInteger()),
        sa.Column('format', sa.String(10)),
        sa.Column('is_lossy', sa.Boolean(), default=False),
        sa.Column('source', sa.String(50)),
        sa.Column('source_url', sa.String(1000)),
        sa.Column('source_quality', sa.String(100)),
        sa.Column('checksum', sa.String(64)),
        sa.Column('imported_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('imported_by', sa.Integer()),
        sa.ForeignKeyConstraint(['album_id'], ['albums.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['imported_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tracks_id', 'tracks', ['id'])
    op.create_index('ix_tracks_album_id', 'tracks', ['album_id'])

    # User albums (many-to-many)
    op.create_table(
        'user_albums',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('album_id', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['album_id'], ['albums.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'album_id')
    )

    # User tracks (many-to-many)
    op.create_table(
        'user_tracks',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'track_id')
    )

    # Activity log
    op.create_table(
        'activity_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer()),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('entity_type', sa.String(50)),
        sa.Column('entity_id', sa.Integer()),
        sa.Column('details', sa.JSON()),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_activity_log_id', 'activity_log', ['id'])
    op.create_index('ix_activity_log_action', 'activity_log', ['action'])
    op.create_index('ix_activity_log_created_at', 'activity_log', ['created_at'])

    # Downloads queue
    op.create_table(
        'downloads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer()),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_url', sa.String(1000)),
        sa.Column('search_query', sa.String(500)),
        sa.Column('search_type', sa.String(20)),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('progress', sa.Integer(), default=0),
        sa.Column('error_message', sa.Text()),
        sa.Column('result_album_id', sa.Integer()),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['result_album_id'], ['albums.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_downloads_id', 'downloads', ['id'])
    op.create_index('ix_downloads_status', 'downloads', ['status'])


def downgrade() -> None:
    op.drop_table('downloads')
    op.drop_table('activity_log')
    op.drop_table('user_tracks')
    op.drop_table('user_albums')
    op.drop_table('tracks')
    op.drop_table('albums')
    op.drop_table('artists')
    op.drop_table('users')
