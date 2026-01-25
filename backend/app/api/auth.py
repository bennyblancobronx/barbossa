"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.services.auth import AuthService
from app.schemas.user import UserLogin, LoginResponse, UserResponse
from app.schemas.common import MessageResponse
from app.models.user import User

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(request: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    auth = AuthService(db)
    user = auth.authenticate(request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = auth.create_token(user.id)

    return LoginResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            created_at=user.created_at,
        ),
    )


@router.post("/logout", response_model=MessageResponse)
def logout(user: User = Depends(get_current_user)):
    """Logout current user (client should discard token)."""
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    """Get current user info."""
    return UserResponse(
        id=user.id,
        username=user.username,
        created_at=user.created_at,
    )
