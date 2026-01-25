"""Phase 3 updates - add notes to pending_review.

Revision ID: 003_phase3_updates
Revises: 002_phase2_downloads
Create Date: 2026-01-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_phase3_updates'
down_revision = '002_phase2_downloads'
branch_labels = None
depends_on = None


def upgrade():
    # Add notes column to pending_review
    op.add_column('pending_review', sa.Column('notes', sa.String(1000), nullable=True))


def downgrade():
    # Remove notes column from pending_review
    op.drop_column('pending_review', 'notes')
