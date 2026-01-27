"""Artist model."""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Artist(Base):
    """Music artist in the library."""

    __tablename__ = "artists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    normalized_name = Column(String(255), nullable=False, index=True)
    sort_name = Column(String(255), index=True)
    path = Column(String(1000))
    artwork_path = Column(String(1000))
    musicbrainz_id = Column(String(36))

    # Extended metadata
    biography = Column(Text)  # Artist bio from Qobuz or other sources
    country = Column(String(2))  # ISO 3166-1 alpha-2 code (US, GB, DE)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    albums = relationship("Album", back_populates="artist", lazy="dynamic")

    def __repr__(self):
        return f"<Artist {self.name}>"
