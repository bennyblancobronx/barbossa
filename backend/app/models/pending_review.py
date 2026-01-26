"""Pending review model for unidentified imports."""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.database import Base


class PendingReviewStatus:
    """Review status values."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MANUAL = "manual"
    FAILED = "failed"  # Import failed after files were moved


class PendingReview(Base):
    """Items awaiting manual review.

    Used when beets cannot confidently identify an album.
    """

    __tablename__ = "pending_review"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String(1000), nullable=False)
    suggested_artist = Column(String(255))
    suggested_album = Column(String(255))
    suggested_year = Column(Integer)
    beets_confidence = Column(Float)  # 0.0 to 1.0
    track_count = Column(Integer)
    quality_info = Column(JSON)  # {sample_rate, bit_depth, format}
    source = Column(String(50))  # Where files came from originally
    source_url = Column(String(1000))  # Original download URL
    status = Column(String(20), default=PendingReviewStatus.PENDING, index=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime(timezone=True))
    error_message = Column(String(1000))
    notes = Column(String(1000))  # Additional notes (e.g., duplicate info)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<PendingReview {self.path} ({self.status})>"
