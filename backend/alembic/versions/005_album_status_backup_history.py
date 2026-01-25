"""Add album status, missing_tracks, and backup_history table

Revision ID: 005
Revises: 004_phase5_exports
Create Date: 2026-01-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '005'
down_revision: Union[str, None] = '004_phase5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add status column to albums (complete, incomplete, pending)
    op.add_column('albums', sa.Column('status', sa.String(20), default='complete'))

    # Add missing_tracks JSON column to albums
    op.add_column('albums', sa.Column('missing_tracks', sa.JSON(), nullable=True))

    # Create backup_history table
    op.create_table(
        'backup_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('destination', sa.String(500), nullable=False),
        sa.Column('destination_type', sa.String(50)),  # local, nas, s3, b2
        sa.Column('status', sa.String(20), nullable=False),  # running, complete, failed
        sa.Column('files_backed_up', sa.Integer(), default=0),
        sa.Column('total_size', sa.BigInteger(), default=0),
        sa.Column('error_message', sa.Text()),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_backup_history_id', 'backup_history', ['id'])
    op.create_index('ix_backup_history_status', 'backup_history', ['status'])
    op.create_index('ix_backup_history_created_at', 'backup_history', ['created_at'])


def downgrade() -> None:
    op.drop_table('backup_history')
    op.drop_column('albums', 'missing_tracks')
    op.drop_column('albums', 'status')
