"""Phase 5 - Export model

Revision ID: 004_phase5
Revises: 003_phase3_updates
Create Date: 2026-01-25

"""
from alembic import op
import sqlalchemy as sa


revision = '004_phase5'
down_revision = '003_phase3_updates'
branch_labels = None
depends_on = None


def upgrade():
    """Create exports table."""
    op.create_table(
        'exports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('destination', sa.String(1000), nullable=False),
        sa.Column('format', sa.String(10), default='flac'),
        sa.Column('include_artwork', sa.Boolean(), default=True),
        sa.Column('include_playlist', sa.Boolean(), default=False),
        sa.Column('status', sa.String(20), default='pending', index=True),
        sa.Column('progress', sa.Integer(), default=0),
        sa.Column('total_albums', sa.Integer(), default=0),
        sa.Column('exported_albums', sa.Integer(), default=0),
        sa.Column('total_size', sa.BigInteger(), default=0),
        sa.Column('celery_task_id', sa.String(100)),
        sa.Column('error_message', sa.String(1000)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    # Index already created by index=True on status column


def downgrade():
    """Drop exports table."""
    op.drop_table('exports')
