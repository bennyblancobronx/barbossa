"""WebSocket API endpoint."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError

from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.websocket import manager

router = APIRouter()


def get_user_from_token(token: str) -> User:
    """Validate JWT and return user."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        user_id = payload.get("sub")

        if not user_id:
            return None

        db = SessionLocal()
        try:
            return db.query(User).filter(User.id == int(user_id)).first()
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

    Message types received (server -> client):
    - heartbeat: Connection keepalive (every 30s)
    - download:progress: Download status updates
    - download:complete: Download finished
    - download:error: Download failed
    - import:complete: Album imported
    - import:review: Album needs review (admin only)
    - activity: User activity (new albums, hearts)
    - notification: User-specific notifications
    - library:updated: Library changes

    Message types sent (client -> server):
    - ping: Request pong response
    - subscribe: Subscribe to specific events
    - unsubscribe: Unsubscribe from events
    """
    # Authenticate
    user = get_user_from_token(token)
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

            if msg_type == "ping":
                # Respond to client ping
                await websocket.send_json({"type": "pong"})

            elif msg_type == "subscribe":
                # Handle subscription requests
                await handle_subscribe(websocket, user, data)

            elif msg_type == "unsubscribe":
                # Handle unsubscription
                await handle_unsubscribe(websocket, user, data)

    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
    except Exception:
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

    elif channel == "library":
        # User subscribing to library updates
        await websocket.send_json({
            "type": "subscribed",
            "channel": "library"
        })

    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown channel: {channel}"
        })


async def handle_unsubscribe(websocket: WebSocket, user: User, data: dict):
    """Handle unsubscription request."""
    channel = data.get("channel")
    await websocket.send_json({
        "type": "unsubscribed",
        "channel": channel
    })
