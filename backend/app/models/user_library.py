"""User library junction tables for hearts."""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Table
from sqlalchemy.sql import func
from app.database import Base

# Album hearts - many-to-many between users and albums
user_albums = Table(
    "user_albums",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("album_id", Integer, ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True),
    Column("added_at", DateTime(timezone=True), server_default=func.now()),
)

# Track hearts - many-to-many between users and tracks
user_tracks = Table(
    "user_tracks",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("track_id", Integer, ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
    Column("added_at", DateTime(timezone=True), server_default=func.now()),
)
