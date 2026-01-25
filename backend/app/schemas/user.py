"""User schemas."""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    """Base user fields."""
    username: str


class UserCreate(UserBase):
    """User creation request."""
    password: str


class UserResponse(UserBase):
    """User response."""
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """Login request."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response with token."""
    token: str
    user: UserResponse
