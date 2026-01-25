"""Activity logging and broadcasting service."""
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.activity import ActivityLog
from app.websocket import broadcast_activity, notify_user


class ActivityService:
    """Service for logging user activities with optional broadcasts."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        user_id: int,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> ActivityLog:
        """Log a user activity (synchronous)."""
        activity = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
        )
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        return activity

    async def log_and_broadcast(
        self,
        user_id: int,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        broadcast: bool = True
    ) -> ActivityLog:
        """Log a user activity and optionally broadcast."""
        activity = self.log(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address
        )

        if broadcast:
            await broadcast_activity({
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "user_id": user_id,
                "details": details
            })

        return activity

    async def log_download_started(
        self,
        user_id: int,
        download_id: int,
        source: str,
        query: str
    ):
        """Log download start."""
        await self.log_and_broadcast(
            user_id=user_id,
            action="download_started",
            entity_type="download",
            entity_id=download_id,
            details={
                "source": source,
                "query": query
            },
            broadcast=False  # Don't broadcast download start
        )

    async def log_album_imported(
        self,
        user_id: int,
        album_id: int,
        artist: str,
        title: str,
        source: str
    ):
        """Log album import and broadcast."""
        await self.log_and_broadcast(
            user_id=user_id,
            action="album_imported",
            entity_type="album",
            entity_id=album_id,
            details={
                "artist": artist,
                "title": title,
                "source": source
            }
        )

    async def log_heart(
        self,
        user_id: int,
        username: str,
        album_id: int,
        artist: str,
        title: str
    ):
        """Log heart action and broadcast."""
        activity = self.log(
            user_id=user_id,
            action="heart",
            entity_type="album",
            entity_id=album_id,
            details={
                "artist": artist,
                "title": title
            }
        )

        # Broadcast to all users (for activity feed)
        await broadcast_activity({
            "action": "heart",
            "username": username,
            "album_id": album_id,
            "artist": artist,
            "title": title
        })

        return activity

    async def log_unheart(
        self,
        user_id: int,
        album_id: int
    ):
        """Log unheart action."""
        return self.log(
            user_id=user_id,
            action="unheart",
            entity_type="album",
            entity_id=album_id
        )

    async def log_track_heart(
        self,
        user_id: int,
        username: str,
        track_id: int,
        artist: str,
        title: str
    ):
        """Log track heart action and broadcast."""
        activity = self.log(
            user_id=user_id,
            action="heart_track",
            entity_type="track",
            entity_id=track_id,
            details={
                "artist": artist,
                "title": title
            }
        )

        await broadcast_activity({
            "action": "heart_track",
            "username": username,
            "track_id": track_id,
            "artist": artist,
            "title": title
        })

        return activity

    async def log_delete(
        self,
        user_id: int,
        album_id: int,
        artist: str,
        title: str
    ):
        """Log album deletion (admin only)."""
        await self.log_and_broadcast(
            user_id=user_id,
            action="delete",
            entity_type="album",
            entity_id=album_id,
            details={
                "artist": artist,
                "title": title
            }
        )

    async def log_quality_upgrade(
        self,
        user_id: int,
        track_id: int,
        old_quality: str,
        new_quality: str
    ):
        """Log quality upgrade."""
        await self.log_and_broadcast(
            user_id=user_id,
            action="quality_upgrade",
            entity_type="track",
            entity_id=track_id,
            details={
                "old_quality": old_quality,
                "new_quality": new_quality
            }
        )

    def get_user_activity(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ActivityLog]:
        """Get activity log for a user."""
        return (
            self.db.query(ActivityLog)
            .filter(ActivityLog.user_id == user_id)
            .order_by(ActivityLog.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_all_activity(
        self,
        limit: int = 100,
        offset: int = 0,
        action: Optional[str] = None,
    ) -> List[ActivityLog]:
        """Get all activity logs (admin)."""
        query = self.db.query(ActivityLog)

        if action:
            query = query.filter(ActivityLog.action == action)

        return (
            query.order_by(ActivityLog.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_recent_activity(self, limit: int = 50) -> List[dict]:
        """Get recent activity for feed display."""
        from app.models.user import User

        activities = (
            self.db.query(ActivityLog, User)
            .join(User, User.id == ActivityLog.user_id)
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": a.id,
                "user_id": a.user_id,
                "username": u.username,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "details": a.details,
                "created_at": a.created_at.isoformat()
            }
            for a, u in activities
        ]
