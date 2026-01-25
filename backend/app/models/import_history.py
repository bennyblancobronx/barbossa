"""Import history model for duplicate detection."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class ImportHistory(Base):
    """Track import history for duplicate detection.

    Uses normalized names to catch variations like:
    - "Dark Side of the Moon" vs "The Dark Side of the Moon"
    - "Dark Side of the Moon (Remaster)" vs "Dark Side of the Moon"
    """

    __tablename__ = "import_history"

    id = Column(Integer, primary_key=True, index=True)
    artist_normalized = Column(String(255), nullable=False, index=True)
    album_normalized = Column(String(255), nullable=False, index=True)
    track_normalized = Column(String(255), index=True)
    source = Column(String(50), nullable=False)
    quality_score = Column(Integer)  # sample_rate * 100 + bit_depth
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="SET NULL"))
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="SET NULL"))
    import_date = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ImportHistory {self.artist_normalized} - {self.album_normalized}>"
