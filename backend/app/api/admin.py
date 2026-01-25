"""Admin API endpoints for user management, health, and backups."""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from passlib.context import CryptContext

from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track
from app.models.activity import ActivityLog
from app.models.backup_history import BackupHistory
from app.schemas.user import UserCreate, UserResponse
from app.services.activity import ActivityService


router = APIRouter(prefix="/admin", tags=["admin"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserUpdate:
    """User update model."""
    def __init__(self, password: Optional[str] = None, is_admin: Optional[bool] = None):
        self.password = password
        self.is_admin = is_admin


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """List all users."""
    return db.query(User).order_by(User.username).all()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Create new user."""
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=data.username,
        password_hash=pwd_context.hash(data.password),
        is_admin=data.is_admin or False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    password: Optional[str] = None,
    is_admin: Optional[bool] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if password:
        user.password_hash = pwd_context.hash(password)

    if is_admin is not None:
        user.is_admin = is_admin

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    admin_count = db.query(User).filter(User.is_admin == True).count()
    if user.is_admin and admin_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete last admin")

    db.delete(user)
    db.commit()

    return {"status": "deleted"}


@router.post("/rescan")
async def rescan_library(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Trigger library rescan."""
    from app.tasks.maintenance import scan_library
    task = scan_library.delay()
    return {"status": "started", "task_id": task.id}


# ============================================================================
# Library Health
# ============================================================================

@router.get("/health")
async def library_health(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get library health report."""
    # Count totals
    artist_count = db.query(func.count(Artist.id)).scalar()
    album_count = db.query(func.count(Album.id)).scalar()
    track_count = db.query(func.count(Track.id)).scalar()
    user_count = db.query(func.count(User.id)).scalar()

    # Quality breakdown
    lossless_count = db.query(func.count(Track.id)).filter(Track.is_lossy == False).scalar()
    lossy_count = db.query(func.count(Track.id)).filter(Track.is_lossy == True).scalar()

    # Storage
    total_size = db.query(func.sum(Track.file_size)).scalar() or 0

    # Incomplete albums
    incomplete_count = db.query(func.count(Album.id)).filter(Album.status == 'incomplete').scalar()

    # Albums by source
    source_counts = db.query(
        Album.source,
        func.count(Album.id)
    ).group_by(Album.source).all()

    return {
        "summary": {
            "artists": artist_count,
            "albums": album_count,
            "tracks": track_count,
            "users": user_count,
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / (1024 ** 3), 2) if total_size else 0
        },
        "quality": {
            "lossless": lossless_count,
            "lossy": lossy_count,
            "lossless_pct": round(lossless_count / track_count * 100, 1) if track_count else 0
        },
        "albums_by_source": {s: c for s, c in source_counts if s},
        "incomplete_albums": incomplete_count,
        "status": "healthy"
    }


# ============================================================================
# Activity Logs
# ============================================================================

@router.get("/activity")
async def list_activity(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get all activity logs (admin only)."""
    service = ActivityService(db)
    activities = service.get_all_activity(limit=limit, offset=offset, action=action)

    return {
        "items": [
            {
                "id": a.id,
                "user_id": a.user_id,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "details": a.details,
                "ip_address": a.ip_address,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in activities
        ],
        "limit": limit,
        "offset": offset
    }


# ============================================================================
# Integrity Verification
# ============================================================================

@router.post("/integrity/verify")
async def verify_integrity(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Trigger integrity verification task."""
    from app.tasks.maintenance import verify_integrity as verify_task
    task = verify_task.delay()
    return {"status": "started", "task_id": task.id}


# ============================================================================
# Backup Management
# ============================================================================

@router.get("/backup/history")
async def backup_history(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get backup history."""
    backups = (
        db.query(BackupHistory)
        .order_by(BackupHistory.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "id": b.id,
                "destination": b.destination,
                "destination_type": b.destination_type,
                "status": b.status,
                "files_backed_up": b.files_backed_up,
                "total_size": b.total_size,
                "error_message": b.error_message,
                "started_at": b.started_at.isoformat() if b.started_at else None,
                "completed_at": b.completed_at.isoformat() if b.completed_at else None,
                "created_at": b.created_at.isoformat() if b.created_at else None
            }
            for b in backups
        ]
    }


@router.post("/backup/trigger")
async def trigger_backup(
    destination: str = Query(..., description="Backup destination path"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Trigger manual backup."""
    from app.tasks.maintenance import run_backup

    # Create backup history record
    backup = BackupHistory(
        destination=destination,
        destination_type="local",
        status="running",
        started_at=datetime.utcnow()
    )
    db.add(backup)
    db.commit()
    db.refresh(backup)

    # Start async backup task
    task = run_backup.delay(backup.id, destination)

    return {
        "status": "started",
        "backup_id": backup.id,
        "task_id": task.id,
        "destination": destination
    }
