"""Track model."""
from sqlalchemy import Column, Integer, String, Boolean, BigInteger, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Track(Base):
    """Individual track with quality metadata."""

    __tablename__ = "tracks"
    __table_args__ = (
        UniqueConstraint('album_id', 'disc_number', 'track_number', name='uq_track_album_position'),
    )

    id = Column(Integer, primary_key=True, index=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False, index=True)
    normalized_title = Column(String(255), nullable=False, index=True)
    track_number = Column(Integer, nullable=False)
    disc_number = Column(Integer, default=1)
    duration = Column(Integer)  # seconds
    path = Column(String(1000), nullable=False)

    # Quality metadata (from ExifTool)
    sample_rate = Column(Integer)  # 44100, 96000, 192000
    bit_depth = Column(Integer)  # 16, 24
    bitrate = Column(Integer)  # kbps for lossy
    channels = Column(Integer, default=2)
    file_size = Column(BigInteger)  # bytes
    format = Column(String(10))  # FLAC, MP3, AAC
    is_lossy = Column(Boolean, default=False)

    # Source tracking
    source = Column(String(50), index=True)  # qobuz, lidarr, youtube, etc.
    source_url = Column(String(1000))
    source_quality = Column(String(100))  # "24/192 FLAC", "320kbps MP3"

    # Integrity
    checksum = Column(String(64))  # BLAKE3 hash

    # Metadata
    lyrics = Column(Text)
    musicbrainz_id = Column(String(36))

    # Extended metadata
    isrc = Column(String(12), index=True)  # International Standard Recording Code
    composer = Column(String(255))  # Important for classical music
    explicit = Column(Boolean, default=False)  # Parental advisory flag

    imported_at = Column(DateTime(timezone=True), server_default=func.now())
    imported_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    album = relationship("Album", back_populates="tracks")

    @property
    def quality_display(self) -> str:
        """Human-readable quality string."""
        fmt = self.format or "Unknown"
        if self.is_lossy:
            bitrate = self.bitrate or 256  # Default assumption for lossy
            return f"{bitrate}kbps {fmt}"
        if self.sample_rate and self.bit_depth:
            return f"{self.bit_depth}/{self.sample_rate // 1000}kHz {fmt}"
        return fmt

    def __repr__(self):
        return f"<Track {self.track_number}. {self.title}>"
