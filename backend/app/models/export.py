"""Export model for user library exports."""
from sqlalchemy import Column, Integer, String, Boolean, BigInteger, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class ExportStatus(str, enum.Enum):
    """Export job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExportFormat(str, enum.Enum):
    """Export format options."""
    FLAC = "flac"
    MP3 = "mp3"
    BOTH = "both"


class Export(Base):
    """User library export job."""

    __tablename__ = "exports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    destination = Column(String(1000), nullable=False)
    format = Column(String(10), default=ExportFormat.FLAC)
    include_artwork = Column(Boolean, default=True)
    include_playlist = Column(Boolean, default=False)

    # Progress tracking
    status = Column(String(20), default=ExportStatus.PENDING, index=True)
    progress = Column(Integer, default=0)  # 0-100
    total_albums = Column(Integer, default=0)
    exported_albums = Column(Integer, default=0)
    total_size = Column(BigInteger, default=0)  # bytes

    # Celery task
    celery_task_id = Column(String(100))

    # Error handling
    error_message = Column(String(1000))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    def __repr__(self):
        return f"<Export {self.id} ({self.status})>"
