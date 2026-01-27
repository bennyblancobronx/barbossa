"""User artists junction table for persistent artist hearts."""
from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.sql import func
from app.database import Base

# User artists - many-to-many between users and artists with auto_add_new flag
user_artists = Table(
    "user_artists",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("artist_id", Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True),
    Column("auto_add_new", Boolean, default=True, nullable=False),
    Column("added_at", DateTime(timezone=True), server_default=func.now()),
)
