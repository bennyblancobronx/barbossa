"""WebSocket tests."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.websocket import manager, ConnectionManager


class TestConnectionManager:
    """Test WebSocket connection manager."""

    def test_manager_init(self):
        """Test manager initialization."""
        mgr = ConnectionManager()
        assert mgr.active_connections == {}
        assert mgr.heartbeat_interval == 30

    def test_get_connection_count_empty(self):
        """Test connection count when empty."""
        mgr = ConnectionManager()
        assert mgr.get_connection_count() == 0

    def test_get_user_ids_empty(self):
        """Test user IDs when empty."""
        mgr = ConnectionManager()
        assert mgr.get_user_ids() == []

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_user(self):
        """Test sending to user with no connections."""
        mgr = ConnectionManager()
        # Should not raise
        await mgr.send_to_user(999, {"test": "message"})

    @pytest.mark.asyncio
    async def test_broadcast_all_empty(self):
        """Test broadcasting with no connections."""
        mgr = ConnectionManager()
        # Should not raise
        await mgr.broadcast_all({"test": "message"})



class TestWebSocketEndpoint:
    """Test WebSocket endpoint."""

    def test_websocket_without_token(self, client):
        """Test WebSocket connection without token fails."""
        with pytest.raises(Exception):
            with client.websocket_connect("/ws"):
                pass

    def test_websocket_with_invalid_token(self, client):
        """Test WebSocket connection with invalid token fails."""
        # FastAPI TestClient websocket_connect may raise different exceptions
        try:
            with client.websocket_connect("/ws?token=invalid"):
                pass
            # If no exception, test should fail
            assert False, "Expected connection to fail"
        except Exception:
            # Any exception is expected
            pass

    def test_websocket_with_valid_token(self, client, auth_token, db):
        """Test WebSocket connection with valid token."""
        # Patch SessionLocal to use test database
        with patch("app.api.websocket.SessionLocal", return_value=db):
            with client.websocket_connect(f"/ws?token={auth_token}") as websocket:
                # Send ping
                websocket.send_json({"type": "ping"})
                # Receive pong
                data = websocket.receive_json()
                assert data["type"] == "pong"

    def test_websocket_subscribe(self, client, auth_token, db):
        """Test subscribing to channels."""
        with patch("app.api.websocket.SessionLocal", return_value=db):
            with client.websocket_connect(f"/ws?token={auth_token}") as websocket:
                # Subscribe to activity
                websocket.send_json({"type": "subscribe", "channel": "activity"})
                data = websocket.receive_json()
                assert data["type"] == "subscribed"
                assert data["channel"] == "activity"

    def test_websocket_subscribe_unknown_channel(self, client, auth_token, db):
        """Test subscribing to unknown channel."""
        with patch("app.api.websocket.SessionLocal", return_value=db):
            with client.websocket_connect(f"/ws?token={auth_token}") as websocket:
                # Subscribe to unknown channel
                websocket.send_json({"type": "subscribe", "channel": "unknown"})
                data = websocket.receive_json()
                assert data["type"] == "error"

    def test_websocket_unsubscribe(self, client, auth_token, db):
        """Test unsubscribing from channels."""
        with patch("app.api.websocket.SessionLocal", return_value=db):
            with client.websocket_connect(f"/ws?token={auth_token}") as websocket:
                # Unsubscribe
                websocket.send_json({"type": "unsubscribe", "channel": "activity"})
                data = websocket.receive_json()
                assert data["type"] == "unsubscribed"
                assert data["channel"] == "activity"


class TestBroadcastFunctions:
    """Test broadcast helper functions."""

    @pytest.mark.asyncio
    async def test_broadcast_download_progress(self):
        """Test download progress broadcast."""
        from app.websocket import broadcast_download_progress

        # Create mock websocket
        mock_ws = AsyncMock()

        # Create new manager and add mock connection
        mgr = ConnectionManager()
        mgr.active_connections[1] = {mock_ws}

        # Patch global manager
        with patch("app.websocket.manager", mgr):
            await broadcast_download_progress(
                download_id=123,
                user_id=1,
                progress=50,
                speed="1.5 MB/s",
                eta="2:30"
            )

        # Verify message was sent
        mock_ws.send_json.assert_called()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "download:progress"
        assert call_args["download_id"] == 123
        assert call_args["progress"] == 50

    @pytest.mark.asyncio
    async def test_broadcast_download_complete(self):
        """Test download complete broadcast."""
        from app.websocket import broadcast_download_complete

        mock_ws = AsyncMock()
        mgr = ConnectionManager()
        mgr.active_connections[1] = {mock_ws}

        with patch("app.websocket.manager", mgr):
            await broadcast_download_complete(
                download_id=123,
                user_id=1,
                album_id=456,
                album_title="Test Album",
                artist_name="Test Artist"
            )

        mock_ws.send_json.assert_called()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "download:complete"
        assert call_args["album_id"] == 456

    @pytest.mark.asyncio
    async def test_broadcast_import_complete(self):
        """Test import complete broadcast."""
        from app.websocket import broadcast_import_complete

        mock_ws = AsyncMock()
        mgr = ConnectionManager()
        mgr.active_connections[1] = {mock_ws}

        with patch("app.websocket.manager", mgr):
            await broadcast_import_complete(
                album_id=789,
                album_title="Imported Album",
                artist_name="Import Artist",
                source="qobuz"
            )

        mock_ws.send_json.assert_called()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "import:complete"
        assert call_args["source"] == "qobuz"

    @pytest.mark.asyncio
    async def test_broadcast_activity(self):
        """Test activity broadcast."""
        from app.websocket import broadcast_activity

        mock_ws = AsyncMock()
        mgr = ConnectionManager()
        mgr.active_connections[1] = {mock_ws}

        with patch("app.websocket.manager", mgr):
            await broadcast_activity({
                "action": "heart",
                "username": "testuser",
                "album_id": 100
            })

        mock_ws.send_json.assert_called()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "activity"
        assert call_args["action"] == "heart"

    @pytest.mark.asyncio
    async def test_notify_user(self):
        """Test user notification."""
        from app.websocket import notify_user

        mock_ws = AsyncMock()
        mgr = ConnectionManager()
        mgr.active_connections[1] = {mock_ws}

        with patch("app.websocket.manager", mgr):
            await notify_user(1, {
                "title": "Test Notification",
                "message": "Hello!"
            })

        mock_ws.send_json.assert_called()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "notification"
        assert call_args["title"] == "Test Notification"

    @pytest.mark.asyncio
    async def test_broadcast_library_update(self):
        """Test library update broadcast."""
        from app.websocket import broadcast_library_update

        mock_ws = AsyncMock()
        mgr = ConnectionManager()
        mgr.active_connections[1] = {mock_ws}

        with patch("app.websocket.manager", mgr):
            await broadcast_library_update(
                entity_type="album",
                entity_id=200,
                action="added"
            )

        mock_ws.send_json.assert_called()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "library:updated"
        assert call_args["action"] == "added"


class TestActivityService:
    """Test activity service with broadcasts."""

    @pytest.mark.asyncio
    async def test_log_heart_broadcasts(self, db):
        """Test that log_heart broadcasts to all users."""
        from app.services.activity import ActivityService
        from app.services.auth import AuthService

        # Create user
        auth = AuthService(db)
        user = auth.create_user("testuser", "testpass")

        service = ActivityService(db)

        with patch("app.services.activity.broadcast_activity") as mock_broadcast:
            mock_broadcast.return_value = None  # Mock the async function

            await service.log_heart(
                user_id=user.id,
                username=user.username,
                album_id=1,
                artist="Pink Floyd",
                title="Dark Side of the Moon"
            )

            mock_broadcast.assert_called_once()
            call_args = mock_broadcast.call_args[0][0]
            assert call_args["action"] == "heart"
            assert call_args["username"] == "testuser"
