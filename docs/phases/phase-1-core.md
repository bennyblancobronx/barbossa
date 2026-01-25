# Phase 1: Core Backend

**Goal:** Working API + CLI with database, authentication, and basic library operations.

**Prerequisites:** Phase 0 complete

---

## Checklist

### 1A: Database & Models
- [x] PostgreSQL running in Docker
- [x] SQLAlchemy models created
- [x] Database migrations working (Alembic)
- [x] Seed data (admin user via CLI)

### 1B: Authentication
- [x] JWT token generation
- [x] Password hashing (bcrypt)
- [x] Login endpoint
- [x] Auth middleware
- [x] Admin check decorator

### 1C: Core Services
- [x] LibraryService (CRUD artists/albums/tracks)
- [x] UserLibraryService (heart/unheart)
- [x] SymlinkService (create/remove links)
- [x] QualityService (extract/compare)

### 1D: API Endpoints
- [x] POST /api/auth/login
- [x] POST /api/auth/logout
- [x] GET /api/auth/me
- [x] GET /api/artists
- [x] GET /api/artists/{id}
- [x] GET /api/artists/{id}/albums
- [x] GET /api/albums
- [x] GET /api/albums/{id}
- [x] GET /api/albums/{id}/tracks
- [x] GET /api/search
- [x] GET /api/me/library
- [x] POST /api/me/library/albums/{id}
- [x] DELETE /api/me/library/albums/{id}

### 1E: CLI Wrapper
- [x] barbossa auth login/logout/whoami
- [x] barbossa library artists/albums/search
- [x] barbossa heart/unheart

### 1F: Tests
- [x] Unit tests for services
- [x] Integration tests for API
- [x] Test fixtures

---

## Implementation Guide

### Step 1: Database Setup

**File: `app/database.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**File: `app/config.py`**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Paths
    music_library: str = "/music/library"
    music_users: str = "/music/users"
    music_downloads: str = "/music/downloads"

    # Qobuz
    qobuz_email: str = ""
    qobuz_password: str = ""
    qobuz_quality: int = 4

    class Config:
        env_file = ".env"

settings = Settings()
```

### Step 2: Models

**File: `app/models/user.py`**

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

**File: `app/models/artist.py`**

```python
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Artist(Base):
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    normalized_name = Column(String(255), nullable=False, index=True)
    sort_name = Column(String(255))
    path = Column(String(1000))
    artwork_path = Column(String(1000))
    musicbrainz_id = Column(String(36))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    albums = relationship("Album", back_populates="artist")
```

**File: `app/models/album.py`**

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Album(Base):
    __tablename__ = "albums"

    id = Column(Integer, primary_key=True, index=True)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False)
    title = Column(String(255), nullable=False, index=True)
    normalized_title = Column(String(255), nullable=False, index=True)
    year = Column(Integer)
    path = Column(String(1000))
    artwork_path = Column(String(1000))
    total_tracks = Column(Integer, default=0)
    available_tracks = Column(Integer, default=0)
    source = Column(String(50))
    is_compilation = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    artist = relationship("Artist", back_populates="albums")
    tracks = relationship("Track", back_populates="album")
```

**File: `app/models/track.py`**

```python
from sqlalchemy import Column, Integer, String, Boolean, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False)
    title = Column(String(255), nullable=False)
    normalized_title = Column(String(255), nullable=False)
    track_number = Column(Integer, nullable=False)
    disc_number = Column(Integer, default=1)
    duration = Column(Integer)  # seconds
    path = Column(String(1000), nullable=False)

    # Quality
    sample_rate = Column(Integer)
    bit_depth = Column(Integer)
    bitrate = Column(Integer)
    channels = Column(Integer, default=2)
    file_size = Column(BigInteger)
    format = Column(String(10))
    is_lossy = Column(Boolean, default=False)

    # Source
    source = Column(String(50))
    source_url = Column(String(1000))
    source_quality = Column(String(100))

    # Integrity
    checksum = Column(String(64))

    imported_at = Column(DateTime(timezone=True), server_default=func.now())
    imported_by = Column(Integer, ForeignKey("users.id"))

    album = relationship("Album", back_populates="tracks")
```

**File: `app/models/user_library.py`**

```python
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Table
from sqlalchemy.sql import func
from app.database import Base

user_albums = Table(
    "user_albums",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("album_id", Integer, ForeignKey("albums.id"), primary_key=True),
    Column("added_at", DateTime(timezone=True), server_default=func.now())
)

user_tracks = Table(
    "user_tracks",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("track_id", Integer, ForeignKey("tracks.id"), primary_key=True),
    Column("added_at", DateTime(timezone=True), server_default=func.now())
)
```

### Step 3: Authentication

**File: `app/services/auth.py`**

```python
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.config import settings
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiry_hours)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None
```

**File: `app/dependencies.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models.user import User

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    return user
```

### Step 4: Core Services

**File: `app/services/library.py`**

```python
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track

class LibraryService:
    def __init__(self, db: Session):
        self.db = db

    def list_artists(self, letter: str = None, page: int = 1, limit: int = 50):
        query = self.db.query(Artist).order_by(Artist.sort_name)

        if letter:
            if letter == "#":
                query = query.filter(~Artist.sort_name.regexp_match("^[A-Za-z]"))
            else:
                query = query.filter(Artist.sort_name.ilike(f"{letter}%"))

        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()

        return {"items": items, "total": total, "page": page}

    def get_artist(self, artist_id: int):
        return self.db.query(Artist).filter(Artist.id == artist_id).first()

    def get_artist_albums(self, artist_id: int):
        return self.db.query(Album).filter(Album.artist_id == artist_id).order_by(Album.year.desc()).all()

    def get_album(self, album_id: int):
        return self.db.query(Album).filter(Album.id == album_id).first()

    def get_album_tracks(self, album_id: int):
        return self.db.query(Track).filter(Track.album_id == album_id).order_by(Track.disc_number, Track.track_number).all()

    def search(self, query: str, type: str = "all", limit: int = 20):
        results = {"artists": [], "albums": [], "tracks": []}
        pattern = f"%{query}%"

        if type in ("all", "artist"):
            results["artists"] = self.db.query(Artist).filter(
                Artist.name.ilike(pattern)
            ).limit(limit).all()

        if type in ("all", "album"):
            results["albums"] = self.db.query(Album).filter(
                Album.title.ilike(pattern)
            ).limit(limit).all()

        if type in ("all", "track"):
            results["tracks"] = self.db.query(Track).filter(
                Track.title.ilike(pattern)
            ).limit(limit).all()

        return results
```

**File: `app/services/user_library.py`**

```python
from sqlalchemy.orm import Session
from sqlalchemy import insert, delete
from app.models.user_library import user_albums, user_tracks
from app.models.album import Album
from app.services.symlink import SymlinkService

class UserLibraryService:
    def __init__(self, db: Session):
        self.db = db
        self.symlink = SymlinkService()

    def get_library(self, user_id: int, page: int = 1, limit: int = 50):
        query = self.db.query(Album).join(
            user_albums,
            Album.id == user_albums.c.album_id
        ).filter(
            user_albums.c.user_id == user_id
        ).order_by(user_albums.c.added_at.desc())

        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()

        return {"items": items, "total": total, "page": page}

    def heart_album(self, user_id: int, album_id: int, username: str):
        # Check not already hearted
        existing = self.db.execute(
            user_albums.select().where(
                user_albums.c.user_id == user_id,
                user_albums.c.album_id == album_id
            )
        ).first()

        if existing:
            return False  # Already hearted

        # Get album for path
        album = self.db.query(Album).filter(Album.id == album_id).first()
        if not album:
            raise ValueError("Album not found")

        # Add to database
        self.db.execute(insert(user_albums).values(
            user_id=user_id,
            album_id=album_id
        ))
        self.db.commit()

        # Create symlinks
        self.symlink.create_album_links(username, album.path)

        return True

    def unheart_album(self, user_id: int, album_id: int, username: str):
        # Get album for path
        album = self.db.query(Album).filter(Album.id == album_id).first()
        if not album:
            return False

        # Remove from database
        self.db.execute(delete(user_albums).where(
            user_albums.c.user_id == user_id,
            user_albums.c.album_id == album_id
        ))
        self.db.commit()

        # Remove symlinks
        self.symlink.remove_album_links(username, album.path)

        return True

    def is_hearted(self, user_id: int, album_id: int) -> bool:
        result = self.db.execute(
            user_albums.select().where(
                user_albums.c.user_id == user_id,
                user_albums.c.album_id == album_id
            )
        ).first()
        return result is not None
```

**File: `app/services/symlink.py`**

```python
import os
import shutil
from pathlib import Path
from app.config import settings

class SymlinkService:
    def __init__(self):
        self.library_path = Path(settings.music_library)
        self.users_path = Path(settings.music_users)

    def create_album_links(self, username: str, album_path: str):
        """Create symlinks (or hardlinks) for album in user's library."""
        source = Path(album_path)
        relative = source.relative_to(self.library_path)
        dest = self.users_path / username / relative

        # Create parent directories
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Try hardlink first, fall back to symlink
        for file in source.iterdir():
            link_path = dest / file.name
            if link_path.exists():
                continue

            try:
                os.link(file, link_path)  # Hardlink
            except OSError:
                os.symlink(file, link_path)  # Symlink fallback

    def remove_album_links(self, username: str, album_path: str):
        """Remove album links from user's library."""
        source = Path(album_path)
        relative = source.relative_to(self.library_path)
        dest = self.users_path / username / relative

        if dest.exists():
            shutil.rmtree(dest)
            self._cleanup_empty_parents(dest.parent, username)

    def _cleanup_empty_parents(self, path: Path, username: str):
        """Remove empty parent directories up to user root."""
        user_root = self.users_path / username
        while path != user_root:
            if path.exists() and not any(path.iterdir()):
                path.rmdir()
                path = path.parent
            else:
                break
```

### Step 5: API Endpoints

**File: `app/api/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.services.auth import authenticate, create_token
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    user: dict

@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate(db, request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(user.id)
    return LoginResponse(
        token=token,
        user={"id": user.id, "username": user.username, "is_admin": user.is_admin}
    )

@router.post("/logout")
def logout():
    return {"message": "Logged out"}

@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "is_admin": user.is_admin}
```

**File: `app/api/library.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.services.library import LibraryService
from app.services.user_library import UserLibraryService
from app.models.user import User

router = APIRouter(prefix="/api", tags=["library"])

@router.get("/artists")
def list_artists(
    letter: str = None,
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = LibraryService(db)
    return service.list_artists(letter, page, limit)

@router.get("/artists/{id}")
def get_artist(id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = LibraryService(db)
    artist = service.get_artist(id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    return artist

@router.get("/artists/{id}/albums")
def get_artist_albums(id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = LibraryService(db)
    return service.get_artist_albums(id)

@router.get("/albums/{id}")
def get_album(id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = LibraryService(db)
    album = service.get_album(id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    # Check if hearted by current user
    user_lib = UserLibraryService(db)
    album.is_hearted = user_lib.is_hearted(user.id, id)

    return album

@router.get("/albums/{id}/tracks")
def get_album_tracks(id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = LibraryService(db)
    return service.get_album_tracks(id)

@router.get("/search")
def search(
    q: str,
    type: str = "all",
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = LibraryService(db)
    return service.search(q, type, limit)

@router.get("/me/library")
def get_user_library(
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = UserLibraryService(db)
    return service.get_library(user.id, page, limit)

@router.post("/me/library/albums/{id}")
def heart_album(id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = UserLibraryService(db)
    try:
        service.heart_album(user.id, id, user.username)
        return {"message": "Album hearted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/me/library/albums/{id}")
def unheart_album(id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = UserLibraryService(db)
    service.unheart_album(user.id, id, user.username)
    return {"message": "Album unhearted"}
```

### Step 6: Main Application

**File: `app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, library

app = FastAPI(
    title="Barbossa",
    description="Family music library manager",
    version="0.1.9"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(library.router)

@app.get("/health")
def health():
    return {"status": "healthy", "version": "0.1.9"}
```

---

## Testing Commands

```bash
# Start services
docker-compose up -d db redis

# Run migrations
docker-compose run --rm barbossa alembic upgrade head

# Start API
docker-compose up barbossa

# Test endpoints
curl http://localhost:8080/health

curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'

# Use returned token
export TOKEN="eyJ..."

curl http://localhost:8080/api/artists \
  -H "Authorization: Bearer $TOKEN"

curl http://localhost:8080/api/me/library \
  -H "Authorization: Bearer $TOKEN"
```

---

## Exit Criteria

- [x] `docker-compose up` starts all services
- [x] Login returns valid JWT token
- [x] Can list artists/albums/tracks
- [x] Can heart/unheart albums
- [x] Symlinks created in user folder
- [x] All tests pass
