"""Common schema patterns."""
from pydantic import BaseModel
from typing import Generic, TypeVar, List

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    items: List[T]
    total: int
    page: int
    limit: int
    pages: int


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
