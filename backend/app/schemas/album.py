"""Album schemas."""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class AlbumBase(BaseModel):
    """Base album fields."""
    title: str
    year: Optional[int] = None


class ArtistBrief(BaseModel):
    """Brief artist info for album responses."""
    id: int
    name: str

    class Config:
        from_attributes = True


class AlbumResponse(AlbumBase):
    """Album response."""
    id: int
    artist_id: int
    path: Optional[str] = None
    artwork_path: Optional[str] = None
    total_tracks: int = 0
    available_tracks: int = 0
    source: Optional[str] = None
    is_hearted: bool = False

    class Config:
        from_attributes = True


class AlbumDetailResponse(AlbumResponse):
    """Album detail with artist info."""
    artist: ArtistBrief
    disc_count: int = 1
    genre: Optional[str] = None
    label: Optional[str] = None
    musicbrainz_id: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlbumListResponse(BaseModel):
    """Paginated album list."""
    items: List[AlbumResponse]
    total: int
    page: int
    limit: int
