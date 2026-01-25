# Rate Limiting Guide

## Overview

Rate limiting protects Barbossa from abuse, ensures fair resource usage, and prevents overloading external APIs (Qobuz, Lidarr, Plex).

## Strategy

| Endpoint Type | Limit | Window | Scope |
|---------------|-------|--------|-------|
| General API | 100 requests | 1 minute | Per user |
| Search (local) | 30 requests | 1 minute | Per user |
| Search (Qobuz) | 10 requests | 1 minute | Global |
| Downloads | 5 concurrent | - | Per user |
| Exports | 1 concurrent | - | Per user |
| Auth (login) | 5 attempts | 5 minutes | Per IP |
| WebSocket | 10 connections | - | Per user |

## Implementation

### Redis-Based Rate Limiter

```python
# app/rate_limiter.py
import redis.asyncio as redis
from fastapi import Request, HTTPException
from typing import Optional
import time

class RateLimiter:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, dict]:
        """
        Check if request is allowed under rate limit.
        Returns (allowed, info) where info contains:
        - remaining: requests remaining in window
        - reset: seconds until window resets
        - limit: max requests per window
        """
        now = time.time()
        window_start = now - window_seconds

        pipe = self.redis.pipeline()

        # Remove old entries outside window
        pipe.zremrangebyscore(key, 0, window_start)

        # Count current entries in window
        pipe.zcard(key)

        # Add current request
        pipe.zadd(key, {str(now): now})

        # Set expiry on key
        pipe.expire(key, window_seconds)

        results = await pipe.execute()
        request_count = results[1]

        # Calculate info
        remaining = max(0, limit - request_count - 1)

        # Get oldest entry to calculate reset time
        oldest = await self.redis.zrange(key, 0, 0, withscores=True)
        if oldest:
            reset = int(oldest[0][1] + window_seconds - now)
        else:
            reset = window_seconds

        info = {
            'remaining': remaining,
            'reset': reset,
            'limit': limit
        }

        if request_count >= limit:
            return False, info

        return True, info

    async def check_concurrent(
        self,
        key: str,
        limit: int
    ) -> tuple[bool, int]:
        """
        Check concurrent operation limit.
        Returns (allowed, current_count)
        """
        current = await self.redis.get(key)
        current_count = int(current) if current else 0

        if current_count >= limit:
            return False, current_count

        return True, current_count

    async def acquire_slot(self, key: str, limit: int, ttl: int = 3600) -> bool:
        """Acquire a concurrent operation slot."""
        allowed, _ = await self.check_concurrent(key, limit)
        if not allowed:
            return False

        await self.redis.incr(key)
        await self.redis.expire(key, ttl)
        return True

    async def release_slot(self, key: str):
        """Release a concurrent operation slot."""
        await self.redis.decr(key)

rate_limiter = RateLimiter(REDIS_URL)
```

### Rate Limit Middleware

```python
# app/middleware/rate_limit.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.rate_limiter import rate_limiter
from app.auth import get_current_user_optional

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Global rate limiting middleware."""

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ['/health', '/health/live', '/health/ready', '/metrics']:
            return await call_next(request)

        # Get user ID or use IP for anonymous requests
        user = await get_current_user_optional(request)
        if user:
            key = f"rate:user:{user.id}"
        else:
            client_ip = request.client.host
            key = f"rate:ip:{client_ip}"

        # Check general rate limit
        allowed, info = await rate_limiter.is_allowed(key, limit=100, window_seconds=60)

        # Add rate limit headers
        response = await call_next(request) if allowed else None

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    'X-RateLimit-Limit': str(info['limit']),
                    'X-RateLimit-Remaining': str(info['remaining']),
                    'X-RateLimit-Reset': str(info['reset']),
                    'Retry-After': str(info['reset'])
                }
            )

        response.headers['X-RateLimit-Limit'] = str(info['limit'])
        response.headers['X-RateLimit-Remaining'] = str(info['remaining'])
        response.headers['X-RateLimit-Reset'] = str(info['reset'])

        return response
```

### Endpoint-Specific Rate Limits

```python
# app/dependencies/rate_limits.py
from fastapi import Depends, HTTPException, Request
from app.rate_limiter import rate_limiter
from app.auth import get_current_user

class RateLimit:
    """Rate limit dependency for specific endpoints."""

    def __init__(self, limit: int, window: int, scope: str = 'user'):
        self.limit = limit
        self.window = window
        self.scope = scope

    async def __call__(self, request: Request, user = Depends(get_current_user)):
        if self.scope == 'user':
            key = f"rate:{request.url.path}:user:{user.id}"
        elif self.scope == 'global':
            key = f"rate:{request.url.path}:global"
        else:
            key = f"rate:{request.url.path}:ip:{request.client.host}"

        allowed, info = await rate_limiter.is_allowed(key, self.limit, self.window)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Try again in {info['reset']} seconds.",
                headers={
                    'X-RateLimit-Limit': str(info['limit']),
                    'X-RateLimit-Remaining': str(info['remaining']),
                    'X-RateLimit-Reset': str(info['reset']),
                    'Retry-After': str(info['reset'])
                }
            )

        return info

# Pre-configured rate limits
search_local_limit = RateLimit(limit=30, window=60, scope='user')
search_qobuz_limit = RateLimit(limit=10, window=60, scope='global')
download_limit = RateLimit(limit=20, window=60, scope='user')
auth_limit = RateLimit(limit=5, window=300, scope='ip')
```

### Usage in Routes

```python
# app/api/downloads.py
from fastapi import APIRouter, Depends
from app.dependencies.rate_limits import search_qobuz_limit, download_limit
from app.rate_limiter import rate_limiter

router = APIRouter(prefix="/api/downloads")

@router.get("/search/qobuz")
async def search_qobuz(
    q: str,
    type: str,
    user = Depends(get_current_user),
    _rate = Depends(search_qobuz_limit)
):
    """Search Qobuz - rate limited to prevent API abuse."""
    # Implementation
    pass

@router.post("/qobuz")
async def download_from_qobuz(
    request: DownloadRequest,
    user = Depends(get_current_user),
    _rate = Depends(download_limit)
):
    """Start Qobuz download - checks concurrent limit."""

    # Check concurrent downloads
    concurrent_key = f"concurrent:downloads:user:{user.id}"
    allowed = await rate_limiter.acquire_slot(concurrent_key, limit=5)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Maximum concurrent downloads reached (5). Wait for a download to complete."
        )

    try:
        # Start download task
        task = download_from_qobuz_task.delay(request.url, user.id)
        return {"task_id": task.id}
    except Exception:
        # Release slot on failure
        await rate_limiter.release_slot(concurrent_key)
        raise
```

### Concurrent Download Tracking

```python
# app/tasks/download.py
from app.rate_limiter import rate_limiter

@celery.task(queue='downloads', bind=True)
def download_from_qobuz_task(self, url: str, user_id: int):
    """Download task with concurrent slot management."""
    concurrent_key = f"concurrent:downloads:user:{user_id}"

    try:
        # Perform download
        result = streamrip_download(url)
        return result
    finally:
        # Always release slot when done
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            rate_limiter.release_slot(concurrent_key)
        )
```

### Login Rate Limiting

```python
# app/api/auth.py
from fastapi import APIRouter, Request, HTTPException, Depends
from app.dependencies.rate_limits import auth_limit

router = APIRouter()

@router.post("/auth/login")
async def login(
    request: Request,
    credentials: LoginRequest,
    _rate = Depends(auth_limit)
):
    """Login with brute-force protection."""

    # Additional lockout after failures
    ip = request.client.host
    lockout_key = f"lockout:ip:{ip}"

    is_locked = await rate_limiter.redis.get(lockout_key)
    if is_locked:
        raise HTTPException(
            status_code=429,
            detail="Account temporarily locked due to too many failed attempts. Try again in 15 minutes."
        )

    # Attempt login
    user = await authenticate(credentials.username, credentials.password)

    if not user:
        # Track failed attempts
        fail_key = f"login_fails:ip:{ip}"
        fails = await rate_limiter.redis.incr(fail_key)
        await rate_limiter.redis.expire(fail_key, 300)

        if fails >= 5:
            # Lock out for 15 minutes
            await rate_limiter.redis.setex(lockout_key, 900, '1')

        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Clear failure count on success
    await rate_limiter.redis.delete(f"login_fails:ip:{ip}")

    return create_tokens(user)
```

### WebSocket Connection Limiting

```python
# app/websocket/manager.py
from app.rate_limiter import rate_limiter

class ConnectionManager:
    MAX_CONNECTIONS_PER_USER = 10

    async def connect(self, websocket: WebSocket, user_id: int) -> bool:
        # Check connection limit
        key = f"ws:connections:user:{user_id}"
        current = len(self.active_connections.get(user_id, set()))

        if current >= self.MAX_CONNECTIONS_PER_USER:
            await websocket.close(code=4029, reason="Too many connections")
            return False

        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)
        return True
```

### External API Rate Limiting

```python
# app/services/external_apis.py
import asyncio
from functools import wraps

class ExternalAPILimiter:
    """Rate limiter for external API calls."""

    def __init__(self):
        self.locks = {}
        self.last_calls = {}

    def rate_limit(self, service: str, calls_per_second: float):
        """Decorator to rate limit external API calls."""
        min_interval = 1.0 / calls_per_second

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if service not in self.locks:
                    self.locks[service] = asyncio.Lock()

                async with self.locks[service]:
                    now = asyncio.get_event_loop().time()
                    last_call = self.last_calls.get(service, 0)

                    elapsed = now - last_call
                    if elapsed < min_interval:
                        await asyncio.sleep(min_interval - elapsed)

                    self.last_calls[service] = asyncio.get_event_loop().time()
                    return await func(*args, **kwargs)

            return wrapper
        return decorator

external_limiter = ExternalAPILimiter()

# Usage
class QobuzService:
    @external_limiter.rate_limit('qobuz', calls_per_second=2)
    async def search(self, query: str, type: str):
        """Search Qobuz - limited to 2 requests per second."""
        pass

class LidarrService:
    @external_limiter.rate_limit('lidarr', calls_per_second=5)
    async def get_queue(self):
        """Get Lidarr queue - limited to 5 requests per second."""
        pass
```

## Configuration

```yaml
# config/barbossa.yml
rate_limits:
  # General API
  api:
    limit: 100
    window: 60
    scope: user

  # Search endpoints
  search:
    local:
      limit: 30
      window: 60
      scope: user
    qobuz:
      limit: 10
      window: 60
      scope: global
    lidarr:
      limit: 20
      window: 60
      scope: global

  # Downloads
  downloads:
    requests:
      limit: 20
      window: 60
      scope: user
    concurrent:
      limit: 5
      scope: user

  # Authentication
  auth:
    login:
      limit: 5
      window: 300
      scope: ip
    lockout:
      threshold: 5
      duration: 900

  # WebSocket
  websocket:
    connections: 10
    messages_per_second: 10

  # External APIs
  external:
    qobuz:
      requests_per_second: 2
    lidarr:
      requests_per_second: 5
    plex:
      requests_per_second: 10
```

## Monitoring Rate Limits

```python
# Add to metrics.py
from prometheus_client import Counter, Gauge

RATE_LIMIT_HITS = Counter(
    'barbossa_rate_limit_hits_total',
    'Total rate limit hits',
    ['endpoint', 'scope']
)

RATE_LIMIT_REMAINING = Gauge(
    'barbossa_rate_limit_remaining',
    'Remaining requests in current window',
    ['endpoint', 'user_id']
)
```

## Response Headers

All rate-limited endpoints return these headers:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed in window |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Seconds until window resets |
| `Retry-After` | Seconds to wait before retrying (on 429) |

## Error Response

```json
{
  "detail": "Rate limit exceeded. Try again in 45 seconds.",
  "error": "rate_limit_exceeded",
  "retry_after": 45
}
```

## Frontend Handling

```typescript
// utils/api.ts
async function fetchWithRateLimit(url: string, options: RequestInit = {}) {
  const response = await fetch(url, options);

  if (response.status === 429) {
    const retryAfter = parseInt(response.headers.get('Retry-After') || '60');

    // Show user-friendly message
    showToast({
      type: 'warning',
      message: `Too many requests. Please wait ${retryAfter} seconds.`,
      duration: retryAfter * 1000
    });

    throw new RateLimitError(retryAfter);
  }

  // Track remaining for UI hints
  const remaining = response.headers.get('X-RateLimit-Remaining');
  if (remaining && parseInt(remaining) < 5) {
    showToast({
      type: 'info',
      message: `${remaining} requests remaining. Slow down to avoid rate limiting.`,
      duration: 3000
    });
  }

  return response;
}
```
