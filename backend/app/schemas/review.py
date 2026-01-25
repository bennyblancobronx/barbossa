"""Review schemas."""
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel


class ReviewResponse(BaseModel):
    """Pending review response."""
    id: int
    path: str
    suggested_artist: Optional[str] = None
    suggested_album: Optional[str] = None
    suggested_year: Optional[int] = None
    beets_confidence: Optional[float] = None
    track_count: Optional[int] = None
    quality_info: Optional[Any] = None
    source: Optional[str] = None
    status: str
    notes: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApproveRequest(BaseModel):
    """Approve import request."""
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None


class RejectRequest(BaseModel):
    """Reject import request."""
    reason: Optional[str] = None
    delete_files: bool = False
