"""Download queue model."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class DownloadStatus(str, enum.Enum):
    """Download status states."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    IMPORTING = "importing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PENDING_REVIEW = "pending_review"  # Low beets confidence, needs manual review


class DownloadSource(str, enum.Enum):
    """Download source types."""
    QOBUZ = "qobuz"
    LIDARR = "lidarr"
    YOUTUBE = "youtube"
    SOUNDCLOUD = "soundcloud"
    BANDCAMP = "bandcamp"
    URL = "url"


class SearchType(str, enum.Enum):
    """Search type for downloads."""
    ARTIST = "artist"
    ALBUM = "album"
    TRACK = "track"


class Download(Base):
    """Download queue entry."""

    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(50), nullable=False)
    source_url = Column(String(1000))
    search_query = Column(String(500))
    search_type = Column(String(20))
    status = Column(String(20), default=DownloadStatus.PENDING.value, index=True)
    progress = Column(Integer, default=0)  # 0-100
    speed = Column(String(50))  # "2.5 MB/s"
    eta = Column(String(50))  # "00:05:32"
    error_message = Column(Text)
    celery_task_id = Column(String(255))
    result_album_id = Column(Integer, ForeignKey("albums.id", ondelete="SET NULL"))
    result_review_id = Column(Integer, ForeignKey("pending_review.id", ondelete="SET NULL"))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<Download {self.id} {self.source} {self.status}>"
