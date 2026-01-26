"""Album schemas."""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.track import TrackResponse


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
    artist_name: Optional[str] = None
    path: Optional[str] = None
    artwork_path: Optional[str] = None
    total_tracks: int = 0
    available_tracks: int = 0
    source: Optional[str] = None
    is_hearted: bool = False


class TrackBrief(BaseModel):
    """Brief track info for album detail responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    track_number: int
    disc_number: int = 1
    duration: Optional[int] = None
    path: Optional[str] = None
    sample_rate: Optional[int] = None
    bit_depth: Optional[int] = None
    format: Optional[str] = None
    is_lossy: bool = False
    quality_display: Optional[str] = None
    is_hearted: bool = False


class AlbumDetailResponse(AlbumResponse):
    """Album detail with artist info and tracks."""
    model_config = ConfigDict(from_attributes=True)

    artist: ArtistBrief
    tracks: List[TrackBrief] = []
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
