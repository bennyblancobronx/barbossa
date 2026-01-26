"""Track schemas."""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class TrackBase(BaseModel):
    """Base track fields."""
    title: str
    track_number: int
    disc_number: int = 1


class TrackResponse(TrackBase):
    """Track response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    album_id: int
    duration: Optional[int] = None
    path: Optional[str] = None

    # Album/Artist context (for player display)
    album_title: Optional[str] = None
    artist_name: Optional[str] = None
    artwork_path: Optional[str] = None

    # Quality
    sample_rate: Optional[int] = None
    bit_depth: Optional[int] = None
    bitrate: Optional[int] = None
    format: Optional[str] = None
    is_lossy: bool = False
    quality_display: Optional[str] = None

    # Source
    source: Optional[str] = None
    source_quality: Optional[str] = None

    # User context
    is_hearted: bool = False

    @classmethod
    def from_orm_with_quality(cls, track, is_hearted: bool = False, include_album: bool = True):
        """Create response with computed quality display and album context.

        Args:
            track: Track ORM object
            is_hearted: Whether user has hearted this track
            include_album: Whether to include album/artist context (for player)
        """
        data = {
            "id": track.id,
            "album_id": track.album_id,
            "title": track.title,
            "track_number": track.track_number,
            "disc_number": track.disc_number,
            "duration": track.duration,
            "path": track.path,
            "sample_rate": track.sample_rate,
            "bit_depth": track.bit_depth,
            "bitrate": track.bitrate,
            "format": track.format,
            "is_lossy": track.is_lossy,
            "source": track.source,
            "source_quality": track.source_quality,
            "quality_display": track.quality_display,
            "is_hearted": is_hearted,
        }

        # Include album/artist context for player display
        if include_album and hasattr(track, 'album') and track.album:
            data["album_title"] = track.album.title
            data["artwork_path"] = track.album.artwork_path
            if hasattr(track.album, 'artist') and track.album.artist:
                data["artist_name"] = track.album.artist.name

        return cls(**data)
