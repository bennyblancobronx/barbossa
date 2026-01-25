# Phase 3: Real-time Updates

**Goal:** WebSocket progress, watch folder monitoring, Celery workers operational.

**Prerequisites:** Phase 2 complete (downloads working)

---

## Checklist

- [ ] WebSocket connection manager
- [ ] Download progress broadcast
- [ ] Activity feed (new albums, hearts, etc.)
- [ ] Watch folder service
- [ ] Celery beat scheduler
- [ ] Plex auto-scan integration
- [ ] Connection heartbeat/reconnection

---

## 1. WebSocket Manager

### app/websocket.py

```python
"""WebSocket connection manager for real-time updates."""
import asyncio
import json
from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime


class ConnectionManager:
    """Manages WebSocket connections per user."""

    def __init__(self):
        # user_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # All admin connections for broadcasts
        self.admin_connections: Set[WebSocket] = set()
        # Heartbeat interval
        self.heartbeat_interval = 30

    async def connect(self, websocket: WebSocket, user_id: int, is_admin: bool = False):
        """Accept connection and register user."""
        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)

        if is_admin:
            self.admin_connections.add(websocket)

        # Start heartbeat
        asyncio.create_task(self._heartbeat(websocket, user_id))

    def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove connection on disconnect."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)

            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

        self.admin_connections.discard(websocket)

    async def send_to_user(self, user_id: int, message: dict):
        """Send message to specific user's connections."""
        if user_id in self.active_connections:
            dead_connections = set()

            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.add(connection)

            # Clean up dead connections
            for conn in dead_connections:
                self.active_connections[user_id].discard(conn)

    async def broadcast_to_admins(self, message: dict):
        """Send message to all admin connections."""
        dead_connections = set()

        for connection in self.admin_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)

        for conn in dead_connections:
            self.admin_connections.discard(conn)

    async def broadcast_all(self, message: dict):
        """Send message to all connected users."""
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, message)

    async def _heartbeat(self, websocket: WebSocket, user_id: int):
        """Send periodic heartbeat to keep connection alive."""
        while websocket in self.active_connections.get(user_id, set()):
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await websocket.send_json({"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()})
            except Exception:
                self.disconnect(websocket, user_id)
                break


# Global instance
manager = ConnectionManager()


# Convenience functions for tasks
async def broadcast_progress(download_id: int, progress: dict):
    """Broadcast download progress to admins."""
    await manager.broadcast_to_admins({
        "type": "download_progress",
        "download_id": download_id,
        **progress
    })


async def broadcast_activity(activity: dict):
    """Broadcast activity to all users."""
    await manager.broadcast_all({
        "type": "activity",
        **activity
    })


async def notify_user(user_id: int, notification: dict):
    """Send notification to specific user."""
    await manager.send_to_user(user_id, {
        "type": "notification",
        **notification
    })
```

---

## 2. WebSocket Endpoint

### app/api/websocket.py

```python
"""WebSocket API endpoint."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from jose import jwt, JWTError

from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.websocket import manager


router = APIRouter()


async def get_user_from_token(token: str) -> User:
    """Validate JWT and return user."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"]
        )
        user_id = payload.get("sub")

        if not user_id:
            return None

        db = SessionLocal()
        try:
            return db.query(User).get(int(user_id))
        finally:
            db.close()

    except JWTError:
        return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """WebSocket connection endpoint.

    Connect with: ws://localhost:8080/ws?token=<jwt>

    Message types received:
    - heartbeat: Connection keepalive
    - download_progress: Download status updates
    - activity: New albums, hearts, etc.
    - notification: User-specific notifications

    Message types sent:
    - subscribe: Subscribe to specific events
    - unsubscribe: Unsubscribe from events
    """
    # Authenticate
    user = await get_user_from_token(token)
    if not user:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Connect
    await manager.connect(websocket, user.id, user.is_admin)

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()

            msg_type = data.get("type")

            if msg_type == "subscribe":
                # Handle subscription requests
                await handle_subscribe(websocket, user, data)

            elif msg_type == "unsubscribe":
                # Handle unsubscription
                await handle_unsubscribe(websocket, user, data)

            elif msg_type == "ping":
                # Respond to client ping
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)


async def handle_subscribe(websocket: WebSocket, user: User, data: dict):
    """Handle subscription request."""
    channel = data.get("channel")

    if channel == "downloads" and user.is_admin:
        # Admin subscribing to all download progress
        await websocket.send_json({
            "type": "subscribed",
            "channel": "downloads"
        })

    elif channel == "activity":
        # User subscribing to activity feed
        await websocket.send_json({
            "type": "subscribed",
            "channel": "activity"
        })


async def handle_unsubscribe(websocket: WebSocket, user: User, data: dict):
    """Handle unsubscription request."""
    channel = data.get("channel")
    await websocket.send_json({
        "type": "unsubscribed",
        "channel": channel
    })
```

---

## 3. Activity Service

### app/services/activity.py

```python
"""Activity logging and broadcasting service."""
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.activity import ActivityLog
from app.websocket import broadcast_activity, notify_user


class ActivityService:
    """Logs and broadcasts user activity."""

    def __init__(self, db: Session):
        self.db = db

    async def log_download_started(
        self,
        user_id: int,
        download_id: int,
        source: str,
        query: str
    ):
        """Log download start."""
        activity = ActivityLog(
            user_id=user_id,
            action="download_started",
            entity_type="download",
            entity_id=download_id,
            details={
                "source": source,
                "query": query
            }
        )
        self.db.add(activity)
        self.db.commit()

    async def log_album_imported(
        self,
        user_id: int,
        album_id: int,
        artist: str,
        title: str,
        source: str
    ):
        """Log album import and broadcast."""
        activity = ActivityLog(
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
        self.db.add(activity)
        self.db.commit()

        # Broadcast to all users
        await broadcast_activity({
            "action": "new_album",
            "album_id": album_id,
            "artist": artist,
            "title": title,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def log_heart(
        self,
        user_id: int,
        username: str,
        album_id: int,
        artist: str,
        title: str
    ):
        """Log heart action and broadcast."""
        activity = ActivityLog(
            user_id=user_id,
            action="heart",
            entity_type="album",
            entity_id=album_id,
            details={
                "artist": artist,
                "title": title
            }
        )
        self.db.add(activity)
        self.db.commit()

        # Broadcast to all users (for activity feed)
        await broadcast_activity({
            "action": "heart",
            "username": username,
            "album_id": album_id,
            "artist": artist,
            "title": title,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def log_unheart(
        self,
        user_id: int,
        album_id: int
    ):
        """Log unheart action."""
        activity = ActivityLog(
            user_id=user_id,
            action="unheart",
            entity_type="album",
            entity_id=album_id
        )
        self.db.add(activity)
        self.db.commit()

    async def log_delete(
        self,
        user_id: int,
        album_id: int,
        artist: str,
        title: str
    ):
        """Log album deletion (admin only)."""
        activity = ActivityLog(
            user_id=user_id,
            action="delete",
            entity_type="album",
            entity_id=album_id,
            details={
                "artist": artist,
                "title": title
            }
        )
        self.db.add(activity)
        self.db.commit()

    def get_recent_activity(self, limit: int = 50) -> list[dict]:
        """Get recent activity for feed."""
        activities = self.db.query(ActivityLog).order_by(
            ActivityLog.created_at.desc()
        ).limit(limit).all()

        return [
            {
                "id": a.id,
                "user_id": a.user_id,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "details": a.details,
                "created_at": a.created_at.isoformat()
            }
            for a in activities
        ]
```

---

## 4. Watch Folder Service

### app/watcher.py

```python
"""Watch folder service for automatic imports."""
import asyncio
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, DirCreatedEvent

from app.config import settings
from app.database import SessionLocal
from app.services.import_service import ImportService
from app.integrations.beets import BeetsClient
from app.integrations.exiftool import ExifToolClient


class ImportWatcher(FileSystemEventHandler):
    """Watches import folder for new albums."""

    def __init__(self):
        self.pending_path = Path(settings.paths_import) / "pending"
        self.processing = set()  # Paths currently being processed
        self.debounce_seconds = 5  # Wait for folder to be complete

    def on_created(self, event):
        """Handle new file/folder creation."""
        if isinstance(event, DirCreatedEvent):
            # New folder - potential album
            asyncio.create_task(self._process_folder(event.src_path))

    async def _process_folder(self, path: str):
        """Process new folder after debounce."""
        folder = Path(path)

        # Skip if already processing
        if str(folder) in self.processing:
            return

        self.processing.add(str(folder))

        try:
            # Wait for folder to stabilize (files still copying)
            await asyncio.sleep(self.debounce_seconds)

            # Check if it has audio files
            audio_extensions = {".flac", ".mp3", ".m4a", ".ogg", ".wav"}
            audio_files = [
                f for f in folder.iterdir()
                if f.suffix.lower() in audio_extensions
            ]

            if not audio_files:
                return

            # Process import
            await self._import_album(folder)

        finally:
            self.processing.discard(str(folder))

    async def _import_album(self, folder: Path):
        """Attempt to import album automatically."""
        db = SessionLocal()

        try:
            beets = BeetsClient()
            exiftool = ExifToolClient()
            import_service = ImportService(db)

            # Identify via beets
            identification = await beets.identify(folder)

            # High confidence - auto import
            if identification["confidence"] >= 0.95:
                # Extract metadata
                tracks_metadata = await exiftool.get_album_metadata(folder)

                # Check duplicates
                existing = await import_service.find_duplicate(
                    identification["artist"],
                    identification["album"]
                )

                if existing:
                    # Move to review with note
                    await self._move_to_review(
                        folder,
                        identification,
                        f"Duplicate of album ID {existing.id}"
                    )
                    return

                # Import
                library_path = await beets.import_album(folder, move=True)
                tracks_metadata = await exiftool.get_album_metadata(library_path)

                await import_service.import_album(
                    path=library_path,
                    tracks_metadata=tracks_metadata,
                    source="import",
                    source_url="",
                    confidence=identification["confidence"]
                )

            else:
                # Low confidence - move to review
                await self._move_to_review(folder, identification)

        finally:
            db.close()

    async def _move_to_review(
        self,
        folder: Path,
        identification: dict,
        note: str = ""
    ):
        """Move folder to review queue."""
        from app.models.pending_review import PendingReview

        review_path = Path(settings.paths_import) / "review" / folder.name
        folder.rename(review_path)

        db = SessionLocal()
        try:
            review = PendingReview(
                path=str(review_path),
                suggested_artist=identification.get("artist"),
                suggested_album=identification.get("album"),
                suggested_year=identification.get("year"),
                beets_confidence=identification.get("confidence", 0),
                file_count=len(list(review_path.iterdir())),
                notes=note
            )
            db.add(review)
            db.commit()
        finally:
            db.close()


def start_watcher():
    """Start the watch folder observer."""
    event_handler = ImportWatcher()
    observer = Observer()

    watch_path = Path(settings.paths_import) / "pending"
    watch_path.mkdir(parents=True, exist_ok=True)

    observer.schedule(event_handler, str(watch_path), recursive=False)
    observer.start()

    return observer


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    observer = start_watcher()

    try:
        while True:
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(1))
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
```

---

## 5. Celery Configuration

### app/worker.py

```python
"""Celery application configuration."""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "barbossa",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.downloads",
        "app.tasks.imports",
        "app.tasks.exports",
        "app.tasks.maintenance"
    ]
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=3,

    # Concurrency
    worker_concurrency=4,
    worker_prefetch_multiplier=1,

    # Beat schedule
    beat_schedule={
        # Scan import folder every 5 minutes
        "scan-import-folder": {
            "task": "app.tasks.imports.scan_import_folder",
            "schedule": crontab(minute="*/5"),
        },

        # Clean up old downloads every hour
        "cleanup-downloads": {
            "task": "app.tasks.maintenance.cleanup_old_downloads",
            "schedule": crontab(minute=0),
        },

        # Verify file integrity daily at 3 AM
        "verify-integrity": {
            "task": "app.tasks.maintenance.verify_integrity",
            "schedule": crontab(hour=3, minute=0),
        },

        # Update album stats weekly
        "update-stats": {
            "task": "app.tasks.maintenance.update_album_stats",
            "schedule": crontab(day_of_week=0, hour=4, minute=0),
        },
    }
)
```

### app/tasks/maintenance.py

```python
"""Maintenance tasks."""
from datetime import datetime, timedelta
from celery import shared_task

from app.database import SessionLocal
from app.models.download import Download, DownloadStatus


@shared_task
def cleanup_old_downloads():
    """Remove download records older than 30 days."""
    db = SessionLocal()

    try:
        cutoff = datetime.utcnow() - timedelta(days=30)

        deleted = db.query(Download).filter(
            Download.created_at < cutoff,
            Download.status.in_([
                DownloadStatus.COMPLETE,
                DownloadStatus.FAILED,
                DownloadStatus.CANCELLED
            ])
        ).delete()

        db.commit()
        return {"deleted": deleted}

    finally:
        db.close()


@shared_task
def verify_integrity():
    """Verify file integrity for all tracks."""
    from pathlib import Path
    import hashlib

    db = SessionLocal()

    try:
        from app.models.track import Track

        issues = []
        tracks = db.query(Track).all()

        for track in tracks:
            path = Path(track.path)

            # Check file exists
            if not path.exists():
                issues.append({
                    "track_id": track.id,
                    "issue": "missing_file",
                    "path": track.path
                })
                continue

            # Verify checksum if stored
            if track.checksum:
                with open(path, "rb") as f:
                    current_hash = hashlib.sha256(f.read()).hexdigest()

                if current_hash != track.checksum:
                    issues.append({
                        "track_id": track.id,
                        "issue": "checksum_mismatch",
                        "expected": track.checksum,
                        "actual": current_hash
                    })

        return {"checked": len(tracks), "issues": issues}

    finally:
        db.close()


@shared_task
def update_album_stats():
    """Recalculate album track counts."""
    db = SessionLocal()

    try:
        from app.models.album import Album
        from app.models.track import Track
        from sqlalchemy import func

        # Get actual track counts
        counts = db.query(
            Track.album_id,
            func.count(Track.id).label("count")
        ).group_by(Track.album_id).all()

        count_map = {c.album_id: c.count for c in counts}

        # Update albums
        updated = 0
        for album in db.query(Album).all():
            actual = count_map.get(album.id, 0)
            if album.available_tracks != actual:
                album.available_tracks = actual
                updated += 1

        db.commit()
        return {"updated": updated}

    finally:
        db.close()
```

### app/tasks/imports.py

```python
"""Import tasks."""
from pathlib import Path
from celery import shared_task

from app.config import settings
from app.database import SessionLocal


@shared_task
def scan_import_folder():
    """Scan import pending folder for new albums."""
    pending_path = Path(settings.paths_import) / "pending"

    if not pending_path.exists():
        return {"scanned": 0, "found": 0}

    audio_extensions = {".flac", ".mp3", ".m4a", ".ogg", ".wav"}
    albums_found = []

    for folder in pending_path.iterdir():
        if folder.is_dir():
            has_audio = any(
                f.suffix.lower() in audio_extensions
                for f in folder.iterdir()
                if f.is_file()
            )

            if has_audio:
                albums_found.append(str(folder))
                # Trigger import via watcher (or process directly)
                process_import.delay(str(folder))

    return {
        "scanned": len(list(pending_path.iterdir())),
        "found": len(albums_found)
    }


@shared_task(bind=True, max_retries=2)
def process_import(self, folder_path: str):
    """Process a single import folder."""
    import asyncio
    from app.integrations.beets import BeetsClient
    from app.integrations.exiftool import ExifToolClient
    from app.services.import_service import ImportService

    async def run():
        folder = Path(folder_path)

        db = SessionLocal()
        try:
            beets = BeetsClient()
            exiftool = ExifToolClient()
            import_service = ImportService(db)

            # Identify
            identification = await beets.identify(folder)

            if identification["confidence"] < 0.95:
                # Move to review
                return {"status": "review", "confidence": identification["confidence"]}

            # Check duplicates
            existing = await import_service.find_duplicate(
                identification["artist"],
                identification["album"]
            )

            if existing:
                return {"status": "duplicate", "existing_id": existing.id}

            # Import
            library_path = await beets.import_album(folder, move=True)
            tracks_metadata = await exiftool.get_album_metadata(library_path)

            album = await import_service.import_album(
                path=library_path,
                tracks_metadata=tracks_metadata,
                source="import",
                source_url="",
                confidence=identification["confidence"]
            )

            return {"status": "imported", "album_id": album.id}

        finally:
            db.close()

    try:
        return asyncio.run(run())
    except Exception as e:
        self.retry(exc=e, countdown=300)
```

---

## 6. Plex Integration

### app/integrations/plex.py

```python
"""Plex integration for library scanning."""
import httpx
from typing import Optional
from app.config import settings


class PlexClient:
    """Plex Media Server API client."""

    def __init__(self):
        self.base_url = settings.plex_url
        self.token = settings.plex_token
        self.music_section = settings.plex_music_section

    @property
    def headers(self) -> dict:
        return {
            "X-Plex-Token": self.token,
            "Accept": "application/json"
        }

    async def test_connection(self) -> bool:
        """Test connection to Plex server."""
        if not self.base_url or not self.token:
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/",
                    headers=self.headers,
                    timeout=10
                )
                return response.status_code == 200
            except Exception:
                return False

    async def get_sections(self) -> list[dict]:
        """Get library sections."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/library/sections",
                headers=self.headers
            )
            response.raise_for_status()

            data = response.json()
            return [
                {
                    "key": section["key"],
                    "title": section["title"],
                    "type": section["type"]
                }
                for section in data.get("MediaContainer", {}).get("Directory", [])
            ]

    async def scan_library(self, section_key: Optional[str] = None, path: Optional[str] = None):
        """Trigger library scan.

        Args:
            section_key: Library section key (defaults to music section)
            path: Optional specific path to scan
        """
        key = section_key or self.music_section

        if not key:
            raise PlexError("No music section configured")

        url = f"{self.base_url}/library/sections/{key}/refresh"

        params = {}
        if path:
            params["path"] = path

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self.headers,
                params=params
            )
            response.raise_for_status()

    async def get_scan_status(self, section_key: Optional[str] = None) -> dict:
        """Get current scan status."""
        key = section_key or self.music_section

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/library/sections/{key}",
                headers=self.headers
            )
            response.raise_for_status()

            data = response.json()
            container = data.get("MediaContainer", {})

            return {
                "scanning": container.get("scanning", False),
                "refreshing": container.get("refreshing", False)
            }


class PlexError(Exception):
    """Plex operation failed."""
    pass


# Auto-scan after import
async def trigger_plex_scan(path: Optional[str] = None):
    """Trigger Plex scan if enabled."""
    if not settings.plex_enabled or not settings.plex_auto_scan:
        return

    client = PlexClient()

    try:
        await client.scan_library(path=path)
    except Exception as e:
        # Log but don't fail - Plex scan is optional
        import logging
        logging.warning(f"Plex scan failed: {e}")
```

---

## 7. Testing

### tests/test_websocket.py

```python
"""WebSocket tests."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app


class TestWebSocket:
    """Test WebSocket connections."""

    def test_connect_with_valid_token(self, client, auth_token):
        """Test WebSocket connection with valid JWT."""
        with client.websocket_connect(f"/ws?token={auth_token}") as websocket:
            # Should receive heartbeat
            data = websocket.receive_json()
            assert data["type"] == "heartbeat"

    def test_connect_with_invalid_token(self, client):
        """Test WebSocket rejection with invalid JWT."""
        with pytest.raises(Exception):
            with client.websocket_connect("/ws?token=invalid"):
                pass

    def test_ping_pong(self, client, auth_token):
        """Test ping/pong messages."""
        with client.websocket_connect(f"/ws?token={auth_token}") as websocket:
            websocket.send_json({"type": "ping"})
            data = websocket.receive_json()
            assert data["type"] == "pong"


class TestActivityBroadcast:
    """Test activity broadcasting."""

    @pytest.mark.asyncio
    async def test_heart_broadcast(self, db_session, test_user, test_album):
        """Test heart action broadcasts to all users."""
        from app.services.activity import ActivityService
        from app.websocket import manager

        # Mock connection
        mock_ws = MagicMock()
        manager.active_connections[test_user.id] = {mock_ws}

        service = ActivityService(db_session)
        await service.log_heart(
            user_id=test_user.id,
            username=test_user.username,
            album_id=test_album.id,
            artist="Pink Floyd",
            title="Dark Side of the Moon"
        )

        # Verify broadcast called
        mock_ws.send_json.assert_called()
```

---

## Validation

Before moving to Phase 4, verify:

1. [ ] WebSocket connects with valid JWT
2. [ ] Heartbeat messages received every 30s
3. [ ] Download progress broadcasts to admins
4. [ ] Activity broadcasts on new albums/hearts
5. [ ] Watch folder detects new albums
6. [ ] Celery beat runs scheduled tasks
7. [ ] Plex scan triggers after import

---

## Exit Criteria

- [ ] WebSocket manager operational
- [ ] Progress updates during downloads
- [ ] Activity feed populates
- [ ] Watch folder auto-imports high-confidence albums
- [ ] Low-confidence imports go to review queue
- [ ] Celery beat scheduler running
- [ ] Maintenance tasks execute on schedule
- [ ] Plex auto-scan working (if configured)
