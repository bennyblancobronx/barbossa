# Phase 0: Foundation

**Goal:** Project setup complete, ready for implementation.

**Prerequisites:** None (this is the starting point)

---

## Checklist

- [x] Requirements documented (contracts.md)
- [x] Integration research complete (14 docs)
- [x] Design system created (design-system.css)
- [x] Blueprint created (BLUEPRINT.md)
- [x] Open questions answered
- [x] docker-compose.yml created
- [x] Database schema created (schema.sql)
- [x] API spec created (openapi.yaml)
- [x] CLI spec created (cli-spec.md)
- [ ] .env.example created
- [x] Backend Dockerfile created
- [x] Frontend Dockerfile created
- [x] Frontend nginx.conf created
- [x] Dependencies listed (requirements.txt, package.json)
- [x] Phase guides created (phases 1-6)

---

## Decisions Recorded

| Question | Decision |
|----------|----------|
| User permissions | Admin/Regular only (1A) |
| Default quality | Tier 4 - max (2A) |
| Auto-heart | Single track only (3B) |
| Playlist management | M3U export only (for now) |
| Metadata editing | Full tags (5B) |
| Artwork upload | Anytime (6B) |
| Downloads | Temporary staging only |
| Search behavior | Auto-fallback to Qobuz after local search |
| Playlist search | Allowed in Downloads only |
| Multi-disc handling | Support disc numbers and disc subfolders |
| Compilation handling | Avoid compilations; use artist "Soundtrack" for soundtracks |
| Mobile app | Not planned (web app only) |

---

## File Structure to Create

```
barbossa/
├── docker-compose.yml          [x] Created
├── .env.example                 [x] Created
├── README.md                    [ ] TODO (brief setup only)
│
├── backend/
│   ├── Dockerfile              [x] Created
│   ├── requirements.txt        [x] Created
│   ├── pyproject.toml          [ ] TODO
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app entry
│   │   ├── config.py           # Settings from env
│   │   ├── database.py         # SQLAlchemy setup
│   │   ├── dependencies.py     # FastAPI dependencies
│   │   ├── worker.py           # Celery app
│   │   ├── watcher.py          # Watch folder service
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py       # Main router
│   │   │   ├── auth.py
│   │   │   ├── artists.py
│   │   │   ├── albums.py
│   │   │   ├── tracks.py
│   │   │   ├── library.py      # User library
│   │   │   ├── downloads.py
│   │   │   ├── admin.py
│   │   │   ├── settings.py
│   │   │   └── websocket.py
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── artist.py
│   │   │   ├── album.py
│   │   │   ├── track.py
│   │   │   ├── download.py
│   │   │   └── activity.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── artist.py
│   │   │   ├── album.py
│   │   │   ├── track.py
│   │   │   └── download.py
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── library.py
│   │   │   ├── user_library.py
│   │   │   ├── download.py
│   │   │   ├── import_service.py
│   │   │   ├── quality.py
│   │   │   ├── symlink.py
│   │   │   └── plex.py
│   │   │
│   │   ├── integrations/
│   │   │   ├── __init__.py
│   │   │   ├── streamrip.py
│   │   │   ├── beets.py
│   │   │   ├── exiftool.py
│   │   │   ├── ytdlp.py
│   │   │   ├── lidarr.py
│   │   │   ├── plex.py
│   │   │   ├── torrentleech.py
│   │   │   └── bandcamp.py
│   │   │
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── downloads.py
│   │   │   ├── imports.py
│   │   │   ├── exports.py
│   │   │   └── maintenance.py
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── normalize.py
│   │       └── paths.py
│   │
│   ├── db/
│   │   ├── schema.sql          [x] Created
│   │   └── init/
│   │       └── 01-schema.sql   # Symlink to schema.sql
│   │
│   ├── api/
│   │   └── openapi.yaml        [x] Created
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_library.py
│       └── test_downloads.py
│
├── frontend/
│   ├── Dockerfile              [x] Created
│   ├── package.json            [x] Created
│   ├── nginx.conf              [x] Created
│   │
│   ├── public/
│   │   └── index.html
│   │
│   └── src/
│       ├── index.js
│       ├── App.js
│       │
│       ├── styles/
│       │   └── design-system.css   [x] Created
│       │
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       ├── services/
│       └── stores/
│
├── cli/
│   ├── setup.py
│   └── barbossa/
│       ├── __init__.py
│       ├── main.py
│       └── commands/
│
└── docs/
    ├── BLUEPRINT.md            [x] Created
    ├── cli-spec.md             [x] Created
    ├── phases/
    │   ├── phase-0-foundation.md   [x] This file
    │   ├── phase-1-core.md
    │   ├── phase-2-downloads.md
    │   ├── phase-3-realtime.md
    │   ├── phase-4-gui.md
    │   ├── phase-5-admin.md
    │   └── phase-6-deploy.md
    └── [integration docs]      [x] Complete
```

---

## Tasks

### 1. Create .env.example

```bash
# Database
DB_PASSWORD=barbossa

# Authentication
JWT_SECRET=change-me-in-production-use-random-string

# Music path (REQUIRED)
MUSIC_PATH=/path/to/your/music

# Qobuz (REQUIRED for downloads)
QOBUZ_EMAIL=your-email@example.com
QOBUZ_PASSWORD=your-password

# Lidarr (optional)
LIDARR_URL=http://lidarr:8686
LIDARR_API_KEY=

# Plex (optional)
PLEX_URL=http://plex:32400
PLEX_TOKEN=
PLEX_MUSIC_SECTION=

# TorrentLeech (optional, admin only)
TORRENTLEECH_KEY=

# Logging
LOG_LEVEL=info
```

### 2. Create Backend Dockerfile

```dockerfile
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    exiftool \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install streamrip
RUN pip install --no-cache-dir streamrip

# Install yt-dlp
RUN pip install --no-cache-dir yt-dlp

# Install beets
RUN pip install --no-cache-dir beets[fetchart,lyrics,lastgenre,chroma]

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app/ ./app/

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 3. Create requirements.txt

```
# Web framework
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-multipart==0.0.6

# Database
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
alembic==1.13.1

# Task queue
celery==5.3.6
redis==5.0.1

# Authentication
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# HTTP client
httpx==0.26.0

# Validation
pydantic==2.5.3
pydantic-settings==2.1.0

# File watching
watchdog==3.0.0

# Audio metadata
mutagen==1.47.0
pyexiftool==0.5.6

# Utilities
python-dotenv==1.0.0

# Testing
pytest==7.4.4
pytest-asyncio==0.23.3
httpx==0.26.0
```

### 4. Create Frontend Dockerfile

```dockerfile
# Build stage
FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 5. Create package.json

```json
{
  "name": "barbossa-frontend",
  "version": "0.1.9",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.0",
    "zustand": "^4.4.7",
    "react-query": "^3.39.3",
    "axios": "^1.6.5",
    "react-h5-audio-player": "^3.9.1"
  },
  "devDependencies": {
    "vite": "^5.0.11",
    "@vitejs/plugin-react": "^4.2.1"
  },
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

---

## Validation

Before moving to Phase 1, verify:

1. [ ] `docker-compose config` passes validation
2. [ ] All files exist in correct locations
3. [ ] .env.example has all required variables
4. [ ] Team has reviewed and approved structure

---

## Exit Criteria

- [x] All foundation files created
- [ ] Docker compose validates
- [x] Ready to begin Phase 1
