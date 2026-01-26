"""Album schemas."""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List


class AlbumBase(BaseModel):
    """Base album fields."""
    title: str
    year: Optional[int] = None


class ArtistBrief(BaseModel):
    """Brief artist info for album responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class AlbumResponse(AlbumBase):
    """Album response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    artist_id: int
    path: Optional[str] = None
    artwork_path: Optional[str] = None
    total_tracks: int = 0
    available_tracks: int = 0
    source: Optional[str] = None
    is_hearted: bool = False


class AlbumDetailResponse(AlbumResponse):
    """Album detail with artist info."""
    model_config = ConfigDict(from_attributes=True)

    artist: ArtistBrief
    disc_count: int = 1
    genre: Optional[str] = None
    label: Optional[str] = None
    musicbrainz_id: Optional[str] = None
    created_at: Optional[datetime] = None


class AlbumListResponse(BaseModel):
    """Paginated album list."""
    items: List[AlbumResponse]
    total: int
    page: int
    limit: int
