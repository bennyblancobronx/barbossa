"""Add checksum column to import_history for content-based deduplication

Revision ID: 017_add_import_history_checksum
Revises: 016_add_album_metadata
Create Date: 2026-01-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '017_add_import_history_checksum'
down_revision: Union[str, None] = '016_add_album_metadata'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Checksum: BLAKE3 hash for content-based deduplication
    # 64 characters for hex-encoded 256-bit hash
    op.add_column('import_history', sa.Column('checksum', sa.String(64)))

    # Index for fast checksum lookups during dedup check
    op.create_index('ix_import_history_checksum', 'import_history', ['checksum'])


def downgrade() -> None:
    op.drop_index('ix_import_history_checksum', 'import_history')
    op.drop_column('import_history', 'checksum')
