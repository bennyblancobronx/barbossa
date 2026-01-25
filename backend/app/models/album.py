"""Album model."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Album(Base):
    """Album in the master library."""

    __tablename__ = "albums"

    id = Column(Integer, primary_key=True, index=True)
    artist_id = Column(Integer, ForeignKey("artists.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False, index=True)
    normalized_title = Column(String(255), nullable=False, index=True)
    year = Column(Integer, index=True)
    path = Column(String(1000))
    artwork_path = Column(String(1000))
    total_tracks = Column(Integer, default=0)
    available_tracks = Column(Integer, default=0)
    disc_count = Column(Integer, default=1)
    genre = Column(String(100))
    label = Column(String(255))
    catalog_number = Column(String(100))
    musicbrainz_id = Column(String(36))
    source = Column(String(50), index=True)  # qobuz, lidarr, youtube, bandcamp, import
    source_url = Column(String(1000))
    is_compilation = Column(Boolean, default=False)
    status = Column(String(20), default='complete')  # complete, incomplete, pending
    missing_tracks = Column(JSON, nullable=True)  # ["Track 11", "Track 12"]
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    artist = relationship("Artist", back_populates="albums")
    tracks = relationship("Track", back_populates="album", lazy="dynamic", order_by="Track.disc_number, Track.track_number")

    def __repr__(self):
        return f"<Album {self.title}>"
