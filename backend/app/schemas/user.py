"""User schemas."""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    """Base user fields."""
    username: str


class UserCreate(UserBase):
    """User creation request."""
    password: str
    is_admin: Optional[bool] = False


class UserResponse(UserBase):
    """User response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_admin: bool = False
    created_at: Optional[datetime] = None


class UserLogin(BaseModel):
    """Login request."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response with token."""
    token: str
    user: UserResponse
