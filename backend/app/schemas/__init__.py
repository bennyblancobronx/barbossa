"""Pydantic schemas for API request/response validation."""
from app.schemas.user import UserCreate, UserResponse, UserLogin, LoginResponse
from app.schemas.artist import ArtistResponse, ArtistListResponse
from app.schemas.album import AlbumResponse, AlbumDetailResponse, AlbumListResponse
from app.schemas.track import TrackResponse
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.download import (
    DownloadCreate,
    DownloadResponse,
    DownloadStatusResponse,
    SearchResult,
    UrlInfo,
)

__all__ = [
    "UserCreate",
    "UserResponse",
    "UserLogin",
    "LoginResponse",
    "ArtistResponse",
    "ArtistListResponse",
    "AlbumResponse",
    "AlbumDetailResponse",
    "AlbumListResponse",
    "TrackResponse",
    "PaginatedResponse",
    "MessageResponse",
    "DownloadCreate",
    "DownloadResponse",
    "DownloadStatusResponse",
    "SearchResult",
    "UrlInfo",
]
