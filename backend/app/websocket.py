"""WebSocket manager for real-time updates.

Per-user tracking with heartbeat for connection keepalive.
"""
import asyncio
from typing import Dict, Set, Optional
from datetime import datetime
from fastapi import WebSocket
from app.database import SessionLocal
from app.models.user import User


class ConnectionManager:
    """Manages WebSocket connections per user."""

    def __init__(self):
        # user_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Heartbeat interval in seconds
        self.heartbeat_interval = 30
        # Track heartbeat tasks for cleanup
        self._heartbeat_tasks: Dict[WebSocket, asyncio.Task] = {}

    async def connect(
        self,
        websocket: WebSocket,
        user_id: int
    ):
        """Accept connection and register user."""
        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)

        # Start heartbeat task
        task = asyncio.create_task(self._heartbeat(websocket, user_id))
        self._heartbeat_tasks[websocket] = task

    def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove connection on disconnect."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)

            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

        # Cancel heartbeat task
        if websocket in self._heartbeat_tasks:
            self._heartbeat_tasks[websocket].cancel()
            del self._heartbeat_tasks[websocket]

    async def send_to_user(self, user_id: int, message: dict):
        """Send message to specific user's connections."""
        if user_id not in self.active_connections:
            return

        dead_connections = set()

        for connection in self.active_connections[user_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)

        # Clean up dead connections
        for conn in dead_connections:
            self.disconnect(conn, user_id)

    async def broadcast_all(self, message: dict):
        """Send message to all connected users."""
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, message)

    async def _heartbeat(self, websocket: WebSocket, user_id: int):
        """Send periodic heartbeat to keep connection alive."""
        try:
            while websocket in self.active_connections.get(user_id, set()):
                await asyncio.sleep(self.heartbeat_interval)
                try:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception:
                    self.disconnect(websocket, user_id)
                    break
        except asyncio.CancelledError:
            pass

    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(len(conns) for conns in self.active_connections.values())

    def get_user_ids(self) -> list:
        """Get list of connected user IDs."""
        return list(self.active_connections.keys())


# Global manager instance
manager = ConnectionManager()


# Convenience functions for broadcasts
async def broadcast_download_progress(
    download_id: int,
    user_id: int,
    progress: int,
    speed: Optional[str] = None,
    eta: Optional[str] = None
):
    """Broadcast download progress to user."""
    message = {
        "type": "download:progress",
        "download_id": download_id,
        "progress": progress,
        "speed": speed,
        "eta": eta,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.send_to_user(user_id, message)


async def broadcast_download_complete(
    download_id: int,
    user_id: int,
    album_id: int,
    album_title: str,
    artist_name: str
):
    """Broadcast download completion."""
    message = {
        "type": "download:complete",
        "download_id": download_id,
        "album_id": album_id,
        "album_title": album_title,
        "artist_name": artist_name,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.send_to_user(user_id, message)


async def broadcast_download_error(
    download_id: int,
    user_id: int,
    error: str
):
    """Broadcast download error."""
    message = {
        "type": "download:error",
        "download_id": download_id,
        "error": error,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.send_to_user(user_id, message)


async def broadcast_import_complete(
    album_id: int,
    album_title: str,
    artist_name: str,
    source: str
):
    """Broadcast album import completion to all users."""
    message = {
        "type": "import:complete",
        "album_id": album_id,
        "album_title": album_title,
        "artist_name": artist_name,
        "source": source,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_all(message)


async def broadcast_activity(activity: dict):
    """Broadcast activity to all users."""
    message = {
        "type": "activity",
        **activity,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_all(message)


async def notify_user(user_id: int, notification: dict):
    """Send notification to specific user."""
    message = {
        "type": "notification",
        **notification,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.send_to_user(user_id, message)


async def broadcast_library_update(
    entity_type: str,
    entity_id: int,
    action: str
):
    """Broadcast library change to all users."""
    message = {
        "type": "library:updated",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_all(message)


async def broadcast_review_needed(
    review_id: int,
    path: str,
    suggested_artist: Optional[str],
    suggested_album: Optional[str],
    confidence: float
):
    """Broadcast to admins when import needs review."""
    message = {
        "type": "import:review",
        "review_id": review_id,
        "path": path,
        "suggested_artist": suggested_artist,
        "suggested_album": suggested_album,
        "confidence": confidence,
        "timestamp": datetime.utcnow().isoformat()
    }
    db = SessionLocal()
    try:
        admin_ids = [
            u.id for u in db.query(User.id).filter(User.is_admin == True).all()
        ]
    finally:
        db.close()

    for admin_id in admin_ids:
        await manager.send_to_user(admin_id, message)
