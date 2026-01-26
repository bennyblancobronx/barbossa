"""Export schemas."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.export import ExportFormat


class ExportCreate(BaseModel):
    """Export creation request."""
    destination: str
    format: ExportFormat = ExportFormat.FLAC
    include_artwork: bool = True
    include_playlist: bool = False
    user_id: Optional[int] = None  # Admin can export for any user


class ExportResponse(BaseModel):
    """Export response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    destination: str
    format: str
    include_artwork: bool
    include_playlist: bool
    status: str
    progress: int
    total_albums: int
    exported_albums: int
    total_size: Optional[int] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
