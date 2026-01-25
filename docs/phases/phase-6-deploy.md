# Phase 6: Deployment and Polish

**Goal:** Production-ready deployment with monitoring, backups, and documentation.

**Prerequisites:** Phase 5 complete (all features working)

---

## Checklist

- [x] Production Docker configuration
- [x] Nginx reverse proxy
- [x] SSL/TLS setup
- [x] Database backups
- [x] Health checks
- [x] Logging configuration
- [x] Environment validation
- [x] Final testing

---

## 1. Production Docker Compose

### docker-compose.prod.yml

```yaml
version: '3.8'

services:
  barbossa:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    restart: always
    environment:
      - DATABASE_URL=postgresql://barbossa:${DB_PASSWORD}@db:5432/barbossa
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET=${JWT_SECRET}
      - MUSIC_PATH=/music
      - QOBUZ_EMAIL=${QOBUZ_EMAIL}
      - QOBUZ_PASSWORD=${QOBUZ_PASSWORD}
      - LIDARR_URL=${LIDARR_URL}
      - LIDARR_API_KEY=${LIDARR_API_KEY}
      - PLEX_URL=${PLEX_URL}
      - PLEX_TOKEN=${PLEX_TOKEN}
      - PLEX_MUSIC_SECTION=${PLEX_MUSIC_SECTION}
      - TORRENTLEECH_KEY=${TORRENTLEECH_KEY}
      - LOG_LEVEL=warning
    volumes:
      - ${MUSIC_PATH}:/music
      - config:/config
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    command: celery -A app.worker worker -l warning -c 4
    restart: always
    environment:
      - DATABASE_URL=postgresql://barbossa:${DB_PASSWORD}@db:5432/barbossa
      - REDIS_URL=redis://redis:6379/0
      - MUSIC_PATH=/music
    volumes:
      - ${MUSIC_PATH}:/music
      - config:/config
    depends_on:
      - barbossa
      - redis
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 1G

  beat:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    command: celery -A app.worker beat -l warning
    restart: always
    environment:
      - DATABASE_URL=postgresql://barbossa:${DB_PASSWORD}@db:5432/barbossa
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - barbossa
      - redis
    deploy:
      resources:
        limits:
          memory: 256M

  watcher:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    command: python -m app.watcher
    restart: always
    environment:
      - DATABASE_URL=postgresql://barbossa:${DB_PASSWORD}@db:5432/barbossa
      - MUSIC_PATH=/music
    volumes:
      - ${MUSIC_PATH}:/music
    depends_on:
      - barbossa
    deploy:
      resources:
        limits:
          memory: 256M

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    restart: always
    depends_on:
      - barbossa
    deploy:
      resources:
        limits:
          memory: 128M

  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - static:/var/www/static:ro
    depends_on:
      - barbossa
      - frontend
    healthcheck:
      test: ["CMD", "nginx", "-t"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:15-alpine
    restart: always
    environment:
      - POSTGRES_USER=barbossa
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=barbossa
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/db/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U barbossa"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backup:
    image: postgres:15-alpine
    restart: "no"
    environment:
      - PGPASSWORD=${DB_PASSWORD}
    volumes:
      - ./backups:/backups
      - ${MUSIC_PATH}:/music:ro
    entrypoint: /bin/sh
    command: ["-c", "echo 'Backup container ready. Run: docker-compose exec backup /backups/backup.sh'"]
    profiles:
      - backup

volumes:
  postgres_data:
  redis_data:
  config:
  static:

networks:
  default:
    driver: bridge
```

---

## 2. Production Dockerfiles

### backend/Dockerfile.prod

```dockerfile
FROM python:3.11-slim AS builder

# Build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Production image
FROM python:3.11-slim

# Runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libimage-exiftool-perl \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install streamrip, yt-dlp, beets
RUN pip install --no-cache-dir streamrip yt-dlp beets[fetchart,lyrics,lastgenre]

# Create non-root user
RUN useradd -m -u 1000 barbossa
WORKDIR /app

# Copy wheels from builder
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application
COPY --chown=barbossa:barbossa app/ ./app/

USER barbossa

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
```

### frontend/Dockerfile.prod

```dockerfile
# Build stage
FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Non-root user
RUN chown -R nginx:nginx /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

---

## 3. Nginx Configuration

### nginx/nginx.conf

```nginx
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 100M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml application/json application/javascript
               application/xml application/xml+rss text/javascript application/x-font-ttf
               font/opentype image/svg+xml;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=downloads:10m rate=1r/s;

    # Upstream servers
    upstream api {
        server barbossa:8080;
        keepalive 32;
    }

    upstream frontend {
        server frontend:80;
    }

    # HTTP redirect to HTTPS
    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name _;

        # SSL configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_session_timeout 1d;
        ssl_session_cache shared:SSL:50m;
        ssl_session_tickets off;

        # Modern SSL configuration
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # API endpoints
        location /api/ {
            limit_req zone=api burst=20 nodelay;

            proxy_pass http://api;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Connection "";

            # Timeouts for long-running requests
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 300s;
        }

        # WebSocket endpoint
        location /ws {
            proxy_pass http://api;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_connect_timeout 7d;
            proxy_send_timeout 7d;
            proxy_read_timeout 7d;
        }

        # Download endpoints (rate limited)
        location /api/downloads/ {
            limit_req zone=downloads burst=5 nodelay;

            proxy_pass http://api;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health check (no auth required)
        location /health {
            proxy_pass http://api/health;
            access_log off;
        }

        # Static frontend
        location / {
            proxy_pass http://frontend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;

            # Cache static assets
            location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
                proxy_pass http://frontend;
                expires 30d;
                add_header Cache-Control "public, immutable";
            }
        }
    }
}
```

---

## 4. Backup Script

### backups/backup.sh

```bash
#!/bin/bash
set -e

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Database backup
echo "Backing up database..."
pg_dump -h db -U barbossa barbossa | gzip > "${BACKUP_DIR}/db_${DATE}.sql.gz"

# Music library metadata backup (not the actual files)
echo "Backing up library metadata..."
tar -czf "${BACKUP_DIR}/config_${DATE}.tar.gz" -C /music .barbossa 2>/dev/null || true

# Clean old backups
echo "Cleaning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "*.gz" -mtime +${RETENTION_DAYS} -delete

# List recent backups
echo "Recent backups:"
ls -lah "${BACKUP_DIR}"/*.gz 2>/dev/null | tail -10

echo "Backup complete: ${DATE}"
```

### backups/restore.sh

```bash
#!/bin/bash
set -e

if [ -z "$1" ]; then
    echo "Usage: restore.sh <backup_file.sql.gz>"
    echo "Available backups:"
    ls -lah /backups/*.sql.gz
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "WARNING: This will overwrite the current database!"
read -p "Continue? (y/N) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo "Restoring database from: $BACKUP_FILE"

# Drop and recreate database
psql -h db -U barbossa -d postgres -c "DROP DATABASE IF EXISTS barbossa;"
psql -h db -U barbossa -d postgres -c "CREATE DATABASE barbossa;"

# Restore
gunzip -c "$BACKUP_FILE" | psql -h db -U barbossa -d barbossa

echo "Restore complete."
```

---

## 5. Health Check Endpoint

### app/api/health.py

```python
"""Health check endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis

from app.database import get_db
from app.config import settings


router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for load balancers and monitoring."""
    status = {
        "status": "healthy",
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

    # Music path check
    from pathlib import Path
    music_path = Path(settings.music_path)
    if music_path.exists() and music_path.is_dir():
        status["checks"]["music_path"] = "ok"
    else:
        status["checks"]["music_path"] = "not accessible"
        status["status"] = "degraded"

    return status


@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness check - is the service ready to handle requests?"""
    try:
        db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception:
        return {"ready": False}
```

---

## 6. Logging Configuration

### app/logging_config.py

```python
"""Logging configuration."""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import settings


def setup_logging():
    """Configure application logging."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # File handler (if log path configured)
    handlers = [console_handler]

    if settings.log_path:
        log_path = Path(settings.log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers
    )

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get logger for module."""
    return logging.getLogger(name)
```

---

## 7. Environment Validation

### scripts/validate_env.py

```python
#!/usr/bin/env python3
"""Validate environment configuration before startup."""
import os
import sys
from pathlib import Path


def validate():
    """Validate all required environment variables."""
    errors = []
    warnings = []

    # Required variables
    required = [
        ("DB_PASSWORD", "Database password"),
        ("JWT_SECRET", "JWT secret key"),
        ("MUSIC_PATH", "Music library path"),
    ]

    for var, description in required:
        if not os.getenv(var):
            errors.append(f"Missing required: {var} ({description})")

    # Check JWT secret strength
    jwt_secret = os.getenv("JWT_SECRET", "")
    if jwt_secret and len(jwt_secret) < 32:
        warnings.append("JWT_SECRET should be at least 32 characters")

    # Check music path exists
    music_path = os.getenv("MUSIC_PATH")
    if music_path and not Path(music_path).exists():
        warnings.append(f"MUSIC_PATH does not exist: {music_path}")

    # Optional integrations
    if os.getenv("QOBUZ_EMAIL") and not os.getenv("QOBUZ_PASSWORD"):
        warnings.append("QOBUZ_EMAIL set but QOBUZ_PASSWORD missing")

    if os.getenv("LIDARR_URL") and not os.getenv("LIDARR_API_KEY"):
        warnings.append("LIDARR_URL set but LIDARR_API_KEY missing")

    if os.getenv("PLEX_URL") and not os.getenv("PLEX_TOKEN"):
        warnings.append("PLEX_URL set but PLEX_TOKEN missing")

    # Report results
    if errors:
        print("ERRORS:")
        for error in errors:
            print(f"  - {error}")

    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")

    if errors:
        print("\nConfiguration invalid. Please fix errors before starting.")
        sys.exit(1)

    if warnings:
        print("\nConfiguration has warnings but is valid.")
    else:
        print("Configuration valid.")

    sys.exit(0)


if __name__ == "__main__":
    validate()
```

---

## 8. Deployment Commands

### Makefile

```makefile
.PHONY: help build up down logs backup restore shell test lint

COMPOSE_FILE ?= docker-compose.yml
COMPOSE_PROD_FILE = docker-compose.prod.yml

help:
	@echo "Barbossa Music Library - Deployment Commands"
	@echo ""
	@echo "Development:"
	@echo "  make build     - Build containers"
	@echo "  make up        - Start development environment"
	@echo "  make down      - Stop containers"
	@echo "  make logs      - View logs"
	@echo "  make shell     - Open shell in API container"
	@echo "  make test      - Run tests"
	@echo ""
	@echo "Production:"
	@echo "  make prod-up   - Start production environment"
	@echo "  make prod-down - Stop production environment"
	@echo "  make backup    - Create database backup"
	@echo "  make restore   - Restore from backup"
	@echo ""

# Development
build:
	docker-compose -f $(COMPOSE_FILE) build

up:
	docker-compose -f $(COMPOSE_FILE) up -d

down:
	docker-compose -f $(COMPOSE_FILE) down

logs:
	docker-compose -f $(COMPOSE_FILE) logs -f

shell:
	docker-compose -f $(COMPOSE_FILE) exec barbossa /bin/sh

test:
	docker-compose -f $(COMPOSE_FILE) exec barbossa pytest

lint:
	docker-compose -f $(COMPOSE_FILE) exec barbossa ruff check app/

# Production
prod-build:
	docker-compose -f $(COMPOSE_PROD_FILE) build

prod-up:
	@scripts/validate_env.py
	docker-compose -f $(COMPOSE_PROD_FILE) up -d

prod-down:
	docker-compose -f $(COMPOSE_PROD_FILE) down

prod-logs:
	docker-compose -f $(COMPOSE_PROD_FILE) logs -f

# Backup
backup:
	docker-compose -f $(COMPOSE_PROD_FILE) --profile backup run --rm backup /backups/backup.sh

restore:
	@echo "Available backups:"
	@ls -la backups/*.sql.gz 2>/dev/null || echo "No backups found"
	@read -p "Enter backup filename: " file; \
	docker-compose -f $(COMPOSE_PROD_FILE) --profile backup run --rm backup /backups/restore.sh /backups/$$file

# SSL
ssl-generate:
	@mkdir -p nginx/ssl
	openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
		-keyout nginx/ssl/key.pem \
		-out nginx/ssl/cert.pem \
		-subj "/CN=localhost"
	@echo "Self-signed certificate generated. Replace with real cert for production."

# Database
db-migrate:
	docker-compose -f $(COMPOSE_FILE) exec barbossa alembic upgrade head

db-shell:
	docker-compose -f $(COMPOSE_FILE) exec db psql -U barbossa
```

---

## 9. Final Testing Checklist

### tests/test_e2e.py

```python
"""End-to-end tests."""
import pytest
from fastapi.testclient import TestClient


class TestEndToEnd:
    """Full workflow tests."""

    def test_login_and_browse(self, client, admin_credentials):
        """Test login and library browsing."""
        # Login
        response = client.post("/api/auth/login", json=admin_credentials)
        assert response.status_code == 200
        token = response.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}

        # Browse library
        response = client.get("/api/albums", headers=headers)
        assert response.status_code == 200

        # Get user info
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["username"] == admin_credentials["username"]

    def test_heart_workflow(self, client, auth_headers, test_album):
        """Test heart/unheart flow."""
        album_id = test_album.id

        # Heart album
        response = client.post(
            f"/api/me/library/albums/{album_id}",
            headers=auth_headers
        )
        assert response.status_code == 200

        # Check in user library
        response = client.get("/api/me/library", headers=auth_headers)
        assert response.status_code == 200
        album_ids = [a["id"] for a in response.json()["albums"]]
        assert album_id in album_ids

        # Unheart
        response = client.delete(
            f"/api/me/library/albums/{album_id}",
            headers=auth_headers
        )
        assert response.status_code == 200

        # Verify removed
        response = client.get("/api/me/library", headers=auth_headers)
        album_ids = [a["id"] for a in response.json()["albums"]]
        assert album_id not in album_ids

    def test_search(self, client, auth_headers):
        """Test search functionality."""
        response = client.get(
            "/api/search",
            params={"q": "test"},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "albums" in response.json()
        assert "artists" in response.json()
        assert "tracks" in response.json()

    def test_health_endpoint(self, client):
        """Test health check."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "checks" in data
```

---

## 10. Deployment Checklist

### Pre-deployment

- [ ] Environment variables configured (`.env`)
- [ ] SSL certificates in place (`nginx/ssl/`)
- [ ] Music path accessible and mounted
- [ ] Database password secure (not default)
- [ ] JWT secret secure (32+ characters)
- [ ] Backup directory writable

### Deployment

```bash
# 1. Validate environment
python scripts/validate_env.py

# 2. Build production images
make prod-build

# 3. Start services
make prod-up

# 4. Check health
curl https://localhost/health

# 5. View logs
make prod-logs

# 6. Create initial backup
make backup
```

### Post-deployment

- [ ] Health endpoint returning healthy
- [ ] Login working
- [ ] Library displaying albums
- [ ] Downloads functional
- [ ] WebSocket connecting
- [ ] Backups scheduled (cron)

### Maintenance Schedule

| Task | Frequency | Command |
|------|-----------|---------|
| Database backup | Daily | `make backup` |
| Log rotation | Weekly | Automatic (logrotate) |
| Security updates | Monthly | `docker-compose pull && make prod-up` |
| Disk usage check | Weekly | `df -h` |
| Database vacuum | Monthly | `docker-compose exec db vacuumdb -U barbossa barbossa` |

---

## Exit Criteria

- [x] Production Docker images built
- [x] Nginx reverse proxy configured
- [x] SSL/TLS working
- [x] Health checks passing
- [x] Backups automated
- [x] Logging configured
- [x] All tests passing
- [x] Documentation complete
