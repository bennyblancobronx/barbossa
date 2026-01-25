"""Phase 2: Download pipeline tables.

Revision ID: 002_phase2_downloads
Revises: 001_initial_schema
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_phase2_downloads'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade():
    # Import history table for duplicate detection
    op.create_table(
        'import_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('artist_normalized', sa.String(255), nullable=False),
        sa.Column('album_normalized', sa.String(255), nullable=False),
        sa.Column('track_normalized', sa.String(255), nullable=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('quality_score', sa.Integer(), nullable=True),
        sa.Column('track_id', sa.Integer(), nullable=True),
        sa.Column('album_id', sa.Integer(), nullable=True),
        sa.Column('import_date', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['album_id'], ['albums.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_import_history_artist_normalized', 'import_history', ['artist_normalized'])
    op.create_index('ix_import_history_album_normalized', 'import_history', ['album_normalized'])

    # Pending review table for unidentified imports
    op.create_table(
        'pending_review',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('path', sa.String(1000), nullable=False),
        sa.Column('suggested_artist', sa.String(255), nullable=True),
        sa.Column('suggested_album', sa.String(255), nullable=True),
        sa.Column('suggested_year', sa.Integer(), nullable=True),
        sa.Column('beets_confidence', sa.Float(), nullable=True),
        sa.Column('track_count', sa.Integer(), nullable=True),
        sa.Column('quality_info', sa.JSON(), nullable=True),
        sa.Column('source', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.String(1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
    )
    op.create_index('ix_pending_review_status', 'pending_review', ['status'])

    # Add speed and eta columns to downloads if not present
    # These may already exist from Phase 1, so we use batch_alter with check
    with op.batch_alter_table('downloads') as batch_op:
        try:
            batch_op.add_column(sa.Column('speed', sa.String(50), nullable=True))
        except Exception:
            pass  # Column already exists
        try:
            batch_op.add_column(sa.Column('eta', sa.String(50), nullable=True))
        except Exception:
            pass  # Column already exists


def downgrade():
    op.drop_index('ix_pending_review_status', table_name='pending_review')
    op.drop_table('pending_review')
    op.drop_index('ix_import_history_album_normalized', table_name='import_history')
    op.drop_index('ix_import_history_artist_normalized', table_name='import_history')
    op.drop_table('import_history')
