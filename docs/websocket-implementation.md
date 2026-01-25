# WebSocket Implementation Guide

## Overview

Barbossa uses WebSockets for real-time updates: download progress, import notifications, library changes, and toast messages. Built on FastAPI's native WebSocket support.

## Architecture

```
+-------------+       WebSocket       +---------------+
|   Frontend  | <------------------> |    Backend    |
|  (React/Vue)|                      |   (FastAPI)   |
+-------------+                      +-------+-------+
                                             |
                                     +-------v-------+
                                     |    Redis      |
                                     |   Pub/Sub     |
                                     +-------+-------+
                                             |
                                     +-------v-------+
                                     | Celery Worker |
                                     +---------------+
```

## Event Types

| Event | Direction | Payload |
|-------|-----------|---------|
| `download:progress` | Server->Client | `{id, progress, speed, eta}` |
| `download:complete` | Server->Client | `{id, album_id, source}` |
| `download:error` | Server->Client | `{id, error, retry_available}` |
| `import:complete` | Server->Client | `{album_id, artist, title}` |
| `import:review` | Server->Client | `{review_id, path, suggestion}` |
| `library:updated` | Server->Client | `{album_id, action}` |
| `quality:upgraded` | Server->Client | `{track_id, old_quality, new_quality}` |
| `export:progress` | Server->Client | `{user_id, progress, current_album}` |
| `export:complete` | Server->Client | `{user_id, path, album_count}` |
| `toast` | Server->Client | `{type, message, duration}` |
| `ping` | Client->Server | `{}` |
| `pong` | Server->Client | `{timestamp}` |

## Backend Implementation

### Connection Manager

```python
# app/websocket/manager.py
from fastapi import WebSocket
from typing import Dict, Set
import json
import asyncio

class ConnectionManager:
    def __init__(self):
        # user_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # For broadcast to all users
        self.all_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)
        self.all_connections.add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

        self.all_connections.discard(websocket)

    async def send_to_user(self, user_id: int, event: str, data: dict):
        """Send event to specific user (all their connections)."""
        message = json.dumps({"event": event, "data": data})

        if user_id in self.active_connections:
            dead_connections = set()

            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                except Exception:
                    dead_connections.add(connection)

            # Clean up dead connections
            for conn in dead_connections:
                self.disconnect(conn, user_id)

    async def broadcast(self, event: str, data: dict):
        """Send event to all connected users."""
        message = json.dumps({"event": event, "data": data})
        dead_connections = []

        for connection in self.all_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.append(connection)

        # Clean up dead connections
        for conn in dead_connections:
            self.all_connections.discard(conn)

    async def broadcast_to_admins(self, event: str, data: dict):
        """Send event only to admin users."""
        # Requires tracking admin status per connection
        pass

# Global instance
manager = ConnectionManager()
```

### WebSocket Endpoint

```python
# app/api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.auth import get_current_user_ws
from app.websocket.manager import manager
import asyncio

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str  # Query param: /ws?token=xxx
):
    # Authenticate
    try:
        user = await get_current_user_ws(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(websocket, user.id)

    try:
        while True:
            # Wait for client messages (ping/pong keepalive)
            data = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=60.0  # 60 second timeout
            )

            message = json.loads(data)

            if message.get("event") == "ping":
                await websocket.send_json({
                    "event": "pong",
                    "data": {"timestamp": datetime.now().isoformat()}
                })

    except asyncio.TimeoutError:
        # No message in 60 seconds, send ping
        try:
            await websocket.send_json({"event": "ping", "data": {}})
        except Exception:
            pass

    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)

    except Exception as e:
        manager.disconnect(websocket, user.id)
```

### Redis Pub/Sub Bridge

```python
# app/websocket/redis_bridge.py
import aioredis
import asyncio
import json
from app.websocket.manager import manager

class RedisPubSubBridge:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.pubsub = None
        self.running = False

    async def start(self):
        """Start listening to Redis pub/sub."""
        redis = await aioredis.from_url(self.redis_url)
        self.pubsub = redis.pubsub()

        # Subscribe to Barbossa channels
        await self.pubsub.subscribe(
            'barbossa:downloads',
            'barbossa:imports',
            'barbossa:library',
            'barbossa:exports',
            'barbossa:toasts'
        )

        self.running = True

        while self.running:
            message = await self.pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0
            )

            if message:
                await self._handle_message(message)

    async def _handle_message(self, message: dict):
        """Route Redis message to WebSocket clients."""
        channel = message['channel'].decode()
        data = json.loads(message['data'])

        event = data.get('event')
        payload = data.get('data', {})
        user_id = data.get('user_id')  # Optional: target specific user

        if user_id:
            await manager.send_to_user(user_id, event, payload)
        else:
            await manager.broadcast(event, payload)

    async def stop(self):
        self.running = False
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()

# Start bridge on app startup
bridge = RedisPubSubBridge(REDIS_URL)

@app.on_event("startup")
async def start_redis_bridge():
    asyncio.create_task(bridge.start())

@app.on_event("shutdown")
async def stop_redis_bridge():
    await bridge.stop()
```

### Publishing Events from Celery

```python
# app/websocket/publisher.py
import redis
import json

redis_client = redis.Redis.from_url(REDIS_URL)

def notify_download_progress(download_id: int, user_id: int, progress: int, speed: str, eta: str):
    """Publish download progress update."""
    redis_client.publish('barbossa:downloads', json.dumps({
        'event': 'download:progress',
        'user_id': user_id,
        'data': {
            'id': download_id,
            'progress': progress,
            'speed': speed,
            'eta': eta
        }
    }))

def notify_download_complete(download_id: int, user_id: int, album_id: int, source: str):
    """Publish download complete event."""
    redis_client.publish('barbossa:downloads', json.dumps({
        'event': 'download:complete',
        'user_id': user_id,
        'data': {
            'id': download_id,
            'album_id': album_id,
            'source': source
        }
    }))

def notify_import_complete(album_id: int, artist: str, title: str):
    """Broadcast new album import (all users)."""
    redis_client.publish('barbossa:imports', json.dumps({
        'event': 'import:complete',
        'data': {
            'album_id': album_id,
            'artist': artist,
            'title': title
        }
    }))

def notify_import_review(review_id: int, path: str, suggestion: str):
    """Notify admins of item needing review."""
    redis_client.publish('barbossa:imports', json.dumps({
        'event': 'import:review',
        'data': {
            'review_id': review_id,
            'path': path,
            'suggestion': suggestion
        }
    }))

def notify_library_updated(album_id: int, action: str):
    """Broadcast library change (all users)."""
    redis_client.publish('barbossa:library', json.dumps({
        'event': 'library:updated',
        'data': {
            'album_id': album_id,
            'action': action  # 'added', 'removed', 'updated'
        }
    }))

def notify_quality_upgraded(track_id: int, user_id: int, old_quality: str, new_quality: str):
    """Notify user of quality upgrade."""
    redis_client.publish('barbossa:library', json.dumps({
        'event': 'quality:upgraded',
        'user_id': user_id,
        'data': {
            'track_id': track_id,
            'old_quality': old_quality,
            'new_quality': new_quality
        }
    }))

def send_toast(user_id: int, toast_type: str, message: str, duration: int = 5000):
    """Send toast notification to user."""
    redis_client.publish('barbossa:toasts', json.dumps({
        'event': 'toast',
        'user_id': user_id,
        'data': {
            'type': toast_type,  # 'success', 'error', 'info', 'warning'
            'message': message,
            'duration': duration
        }
    }))

def broadcast_toast(toast_type: str, message: str, duration: int = 5000):
    """Send toast to all users."""
    redis_client.publish('barbossa:toasts', json.dumps({
        'event': 'toast',
        'data': {
            'type': toast_type,
            'message': message,
            'duration': duration
        }
    }))
```

### Usage in Celery Tasks

```python
# app/tasks/download.py
from app.websocket.publisher import (
    notify_download_progress,
    notify_download_complete,
    send_toast
)

@celery.task(queue='downloads')
def download_from_qobuz(url: str, user_id: int, download_id: int):
    """Download with progress updates."""

    def on_progress(progress: int, speed: str, eta: str):
        notify_download_progress(download_id, user_id, progress, speed, eta)

    try:
        # Download with progress callback
        result = streamrip_download(url, progress_callback=on_progress)

        # Import and get album_id
        album_id = process_import(result.path, user_id)

        # Notify complete
        notify_download_complete(download_id, user_id, album_id, 'qobuz')
        send_toast(user_id, 'success', f'Downloaded: {result.album_name}')

    except Exception as e:
        redis_client.publish('barbossa:downloads', json.dumps({
            'event': 'download:error',
            'user_id': user_id,
            'data': {
                'id': download_id,
                'error': str(e),
                'retry_available': True
            }
        }))
        send_toast(user_id, 'error', f'Download failed: {str(e)}')
        raise
```

## Frontend Implementation

### WebSocket Hook (React)

```typescript
// hooks/useWebSocket.ts
import { useEffect, useRef, useCallback, useState } from 'react';
import { useAuth } from './useAuth';

interface WebSocketMessage {
  event: string;
  data: any;
}

type EventHandler = (data: any) => void;

export function useWebSocket() {
  const { token } = useAuth();
  const ws = useRef<WebSocket | null>(null);
  const handlers = useRef<Map<string, Set<EventHandler>>>(new Map());
  const [connected, setConnected] = useState(false);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  const connect = useCallback(() => {
    if (!token) return;

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws?token=${token}`;

    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      setConnected(true);
      reconnectAttempts.current = 0;

      // Start ping interval
      const pingInterval = setInterval(() => {
        if (ws.current?.readyState === WebSocket.OPEN) {
          ws.current.send(JSON.stringify({ event: 'ping' }));
        }
      }, 30000);

      ws.current!.onclose = () => {
        clearInterval(pingInterval);
        setConnected(false);

        // Reconnect with backoff
        if (reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
          reconnectAttempts.current++;
          setTimeout(connect, delay);
        }
      };
    };

    ws.current.onmessage = (event) => {
      const message: WebSocketMessage = JSON.parse(event.data);

      const eventHandlers = handlers.current.get(message.event);
      if (eventHandlers) {
        eventHandlers.forEach(handler => handler(message.data));
      }
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }, [token]);

  const subscribe = useCallback((event: string, handler: EventHandler) => {
    if (!handlers.current.has(event)) {
      handlers.current.set(event, new Set());
    }
    handlers.current.get(event)!.add(handler);

    // Return unsubscribe function
    return () => {
      handlers.current.get(event)?.delete(handler);
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      ws.current?.close();
    };
  }, [connect]);

  return { connected, subscribe };
}
```

### Event Handlers (React)

```typescript
// hooks/useDownloadEvents.ts
import { useEffect } from 'react';
import { useWebSocket } from './useWebSocket';
import { useDownloadStore } from '../stores/downloads';
import { useToastStore } from '../stores/toasts';

export function useDownloadEvents() {
  const { subscribe } = useWebSocket();
  const { updateProgress, markComplete, markError } = useDownloadStore();
  const { addToast } = useToastStore();

  useEffect(() => {
    const unsubProgress = subscribe('download:progress', (data) => {
      updateProgress(data.id, data.progress, data.speed, data.eta);
    });

    const unsubComplete = subscribe('download:complete', (data) => {
      markComplete(data.id, data.album_id);
    });

    const unsubError = subscribe('download:error', (data) => {
      markError(data.id, data.error);
    });

    return () => {
      unsubProgress();
      unsubComplete();
      unsubError();
    };
  }, [subscribe, updateProgress, markComplete, markError]);
}

// hooks/useToastEvents.ts
export function useToastEvents() {
  const { subscribe } = useWebSocket();
  const { addToast } = useToastStore();

  useEffect(() => {
    const unsub = subscribe('toast', (data) => {
      addToast({
        type: data.type,
        message: data.message,
        duration: data.duration
      });
    });

    return unsub;
  }, [subscribe, addToast]);
}

// hooks/useLibraryEvents.ts
export function useLibraryEvents() {
  const { subscribe } = useWebSocket();
  const { refetchLibrary } = useLibraryStore();

  useEffect(() => {
    const unsubImport = subscribe('import:complete', (data) => {
      refetchLibrary();
    });

    const unsubUpdate = subscribe('library:updated', (data) => {
      refetchLibrary();
    });

    return () => {
      unsubImport();
      unsubUpdate();
    };
  }, [subscribe, refetchLibrary]);
}
```

### Toast Component

```tsx
// components/ToastContainer.tsx
import { useToastStore } from '../stores/toasts';
import { useToastEvents } from '../hooks/useToastEvents';
import { useEffect } from 'react';

const TOAST_ICONS = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ℹ'
};

const TOAST_COLORS = {
  success: 'bg-green-600',
  error: 'bg-red-600',
  warning: 'bg-yellow-600',
  info: 'bg-blue-600'
};

export function ToastContainer() {
  useToastEvents();
  const { toasts, removeToast } = useToastStore();

  return (
    <div className="fixed bottom-20 right-4 z-50 space-y-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`${TOAST_COLORS[toast.type]} text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 animate-slide-in`}
        >
          <span className="text-lg">{TOAST_ICONS[toast.type]}</span>
          <span>{toast.message}</span>
          <button
            onClick={() => removeToast(toast.id)}
            className="ml-2 opacity-70 hover:opacity-100"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
```

### Connection Status Indicator

```tsx
// components/ConnectionStatus.tsx
import { useWebSocket } from '../hooks/useWebSocket';

export function ConnectionStatus() {
  const { connected } = useWebSocket();

  if (connected) return null;

  return (
    <div className="fixed top-0 left-0 right-0 bg-yellow-600 text-white text-center py-1 text-sm z-50">
      Reconnecting to server...
    </div>
  );
}
```

## Security Considerations

1. **Authentication**: Validate JWT token on WebSocket connection
2. **Authorization**: Filter events by user permissions (admin-only events)
3. **Rate limiting**: Limit client messages to prevent abuse
4. **Message validation**: Sanitize all incoming messages
5. **Connection limits**: Max connections per user (e.g., 5)
6. **Heartbeat**: Detect and clean up stale connections

## Testing

```python
# tests/test_websocket.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_websocket_connect():
    client = TestClient(app)
    with client.websocket_connect(f"/ws?token={valid_token}") as websocket:
        # Send ping
        websocket.send_json({"event": "ping"})

        # Receive pong
        data = websocket.receive_json()
        assert data["event"] == "pong"
        assert "timestamp" in data["data"]

def test_websocket_unauthorized():
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws?token=invalid"):
            pass
```
