"""Authentication service."""
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.config import settings
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Authentication and authorization service."""

    def __init__(self, db: Session):
        self.db = db

    def verify_password(self, plain: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain, hashed)

    def hash_password(self, password: str) -> str:
        """Hash a password for storage."""
        return pwd_context.hash(password)

    def create_token(self, user_id: int) -> str:
        """Create a JWT token for a user."""
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiry_hours)
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    def decode_token(self, token: str) -> Optional[int]:
        """Decode a JWT token and return user_id, or None if invalid."""
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            return int(payload.get("sub"))
        except (JWTError, ValueError):
            return None

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user by username and password."""
        user = self.db.query(User).filter(User.username == username).first()
        if user and self.verify_password(password, user.password_hash):
            return user
        return None

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get a user by ID."""
        return self.db.query(User).filter(User.id == user_id).first()

    def create_user(self, username: str, password: str) -> User:
        """Create a new user."""
        user = User(
            username=username,
            password_hash=self.hash_password(password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
