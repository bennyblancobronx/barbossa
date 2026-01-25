"""Health check endpoints for monitoring and load balancers."""
from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis

from app.database import get_db
from app.config import settings
from app import __version__


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint for load balancers and monitoring.

    Returns status of all critical dependencies.
    """
    status = {
        "status": "healthy",
        "version": __version__,
        "checks": {}
    }

    # Database check
    try:
        db.execute(text("SELECT 1"))
        status["checks"]["database"] = "ok"
    except Exception as e:
        status["checks"]["database"] = f"error: {str(e)}"
        status["status"] = "unhealthy"

    # Redis check
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
        status["checks"]["redis"] = "ok"
    except Exception as e:
        status["checks"]["redis"] = f"error: {str(e)}"
        status["status"] = "unhealthy"

    # Music library path check
    music_path = Path(settings.music_library)
    if music_path.exists() and music_path.is_dir():
        status["checks"]["music_library"] = "ok"
    else:
        status["checks"]["music_library"] = "not accessible"
        status["status"] = "degraded"

    # Users directory check
    users_path = Path(settings.music_users)
    if users_path.exists() and users_path.is_dir():
        status["checks"]["music_users"] = "ok"
    else:
        status["checks"]["music_users"] = "not accessible"
        if status["status"] == "healthy":
            status["status"] = "degraded"

    return status


@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness check - is the service ready to handle requests?

    Used by Kubernetes/orchestrators to determine if traffic can be routed.
    """
    try:
        db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception:
        return {"ready": False}


@router.get("/live")
def liveness_check():
    """
    Liveness check - is the process alive?

    Simple check that the application is running.
    """
    return {"alive": True, "version": __version__}
