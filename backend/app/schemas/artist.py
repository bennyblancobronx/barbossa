"""Artist schemas."""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List


class ArtistBase(BaseModel):
    """Base artist fields."""
    name: str


class ArtistResponse(ArtistBase):
    """Artist response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    sort_name: Optional[str] = None
    path: Optional[str] = None
    artwork_path: Optional[str] = None
    musicbrainz_id: Optional[str] = None


class ArtistListResponse(BaseModel):
    """Paginated artist list."""
    items: List[ArtistResponse]
    total: int
    page: int
    limit: int
