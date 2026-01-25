"""Download request/response schemas."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, HttpUrl, field_validator


class DownloadCreate(BaseModel):
    """Create download request."""
    url: str
    quality: Optional[int] = 4  # 0-4 for Qobuz
    confirm_lossy: Optional[bool] = False
    search_type: Optional[str] = None  # artist, album, track, playlist

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v):
        if v is not None and not 0 <= v <= 4:
            raise ValueError("Quality must be between 0 and 4")
        return v

    @field_validator("search_type")
    @classmethod
    def validate_search_type(cls, v):
        if v is not None and v not in ("artist", "album", "track", "playlist"):
            raise ValueError("Invalid search type")
        return v


class DownloadResponse(BaseModel):
    """Download response."""
    id: int
    user_id: int
    source: str
    source_url: Optional[str] = None
    search_query: Optional[str] = None
    search_type: Optional[str] = None
    status: str
    progress: int
    speed: Optional[str] = None
    eta: Optional[str] = None
    error_message: Optional[str] = None
    result_album_id: Optional[int] = None
    celery_task_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    """Qobuz search result."""
    id: str
    title: str
    artist: str
    year: Optional[str] = None
    quality: Optional[int] = None  # Max bit depth
    url: str


class QobuzSearchParams(BaseModel):
    """Qobuz search parameters."""
    q: str
    type: str = "album"
    limit: int = 20

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in ("artist", "album", "track", "playlist"):
            raise ValueError("Type must be artist, album, track, or playlist")
        return v

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):
        if not 1 <= v <= 100:
            raise ValueError("Limit must be between 1 and 100")
        return v


class UrlInfo(BaseModel):
    """URL metadata info."""
    title: str
    artist: str
    album: Optional[str] = None
    duration: Optional[int] = None
    is_lossy: bool = True
    thumbnail: Optional[str] = None
    source: str


class DownloadStatusResponse(BaseModel):
    """Download status for polling."""
    id: int
    status: str
    progress: int
    speed: Optional[str] = None
    eta: Optional[str] = None
    error_message: Optional[str] = None
    result_album_id: Optional[int] = None

    class Config:
        from_attributes = True
