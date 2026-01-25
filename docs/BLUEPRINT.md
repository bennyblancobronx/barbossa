# BARBOSSA BLUEPRINT v0.1.9

**A family web-app that runs on Docker and manages a centralized music library.**

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Requirements Audit](#2-requirements-audit)
3. [Architecture Decision](#3-architecture-decision)
4. [System Components](#4-system-components)
5. [Phase Breakdown](#5-phase-breakdown)
6. [Data Models](#6-data-models)
7. [API Contract](#7-api-contract)
8. [CLI Contract](#8-cli-contract)
9. [Integration Matrix](#9-integration-matrix)
10. [Open Questions](#10-open-questions)
11. [Risk Assessment](#11-risk-assessment)
12. [Acceptance Criteria](#12-acceptance-criteria)

---

## 1. EXECUTIVE SUMMARY

### What Barbossa IS
- Family music library manager (Docker)
- Multi-source downloader (Qobuz primary)
- Per-user collections via symlinks/hardlinks
- Plex-compatible organization
- Quality-aware duplicate detection

### What Barbossa is NOT
- NOT a music player (use Plex/Plexamp)
- NOT a streaming service
- NOT replacing existing infrastructure

### Core Principle
**API-First**: Every operation works via API before GUI exists. CLI wraps API. GUI consumes API.

---

## 2. REQUIREMENTS AUDIT

### 2.1 Pages Required

| Page | Status | Notes |
|------|--------|-------|
| Master Library | DEFINED | Artist grid, album view, track view |
| User Library | DEFINED | Identical to Master, filtered to user's hearts |
| Downloads | DEFINED | Search + URL paste field (auto-fallback to Qobuz) |
| Settings | DEFINED | Admin only, paths/users/integrations |
| Export | PARTIAL | Need: format options, destination picker |

### 2.2 Feature Checklist

| Feature | Status | Doc Reference |
|---------|--------|---------------|
| Symlink/hardlink user libraries | DEFINED | contracts.md |
| Qobuz download (streamrip) | DEFINED | docs/streamrip-integration.md |
| Lidarr integration | DEFINED | docs/lidarr-integration.md |
| YouTube/Soundcloud (yt-dlp) | DEFINED | docs/ytdlp-integration.md |
| Bandcamp purchases | DEFINED | docs/bandcamp-integration.md |
| Bandcamp free (yt-dlp) | DEFINED | docs/ytdlp-integration.md |
| Beets import pipeline | DEFINED | docs/beets-integration.md |
| ExifTool quality extraction | DEFINED | docs/exiftool-integration.md |
| Plex auto-scan | DEFINED | docs/plex-integration.md |
| TorrentLeech upload (admin) | DEFINED | docs/torrentleech-integration.md |
| Custom artwork upload | PARTIAL | Mentioned, not fully spec'd |
| Metadata editing | PARTIAL | Mentioned, not fully spec'd |
| Playlist management (M3U export only) | DEFINED | Export-only for now |
| Dedupe detection | DEFINED | contracts.md, exiftool doc |
| WebSocket real-time updates | DEFINED | docs/websocket-implementation.md |
| Preview player (persists) | PARTIAL | Player bar defined, persistence not |
| Export to external drive | PARTIAL | Mentioned, not fully spec'd |

### 2.3 Interface Requirements Audit

| Requirement | Status | Notes |
|-------------|--------|-------|
| Square album art, rounded corners | DEFINED | design-system.css (8px radius) |
| Artist name only (no album count) | DEFINED | album-card component |
| Heart on album (bottom left) | DEFINED | album-card-heart class |
| Trash on album (top left, 1s delay) | DEFINED | 1s hover delay per contracts.md |
| A-Z sidebar | DEFINED | az-index component |
| Track row: Heart, Number, Title | DEFINED | track-row component |
| Search in header right | DEFINED | header-search component |
| Search type selection | DEFINED | segmented control |
| Toast notifications | DEFINED | toast component (not modal) |
| Player persists across pages | PARTIAL | Player bar defined, state persistence TBD |

### 2.4 Settings Requirements Audit

| Setting | Status | Notes |
|---------|--------|-------|
| Music library location | DEFINED | Path config |
| User management | PARTIAL | CRUD defined, permissions TBD |
| Streamrip quality | DEFINED | 0-4 tier system |
| Streamrip download settings | PARTIAL | Need full config exposure |
| Download folders | DEFINED | qobuz/lidarr/youtube/bandcamp |
| Watch folder (torrent) | DEFINED | Lidarr integration |
| Usenet folder | DEFINED | Lidarr integration |
| Barbossa DL location | DEFINED | /music/downloads |

### 2.5 Missing/Unclear Requirements

| Item | Question | Impact |
|------|----------|--------|
| User permissions | Admin vs regular user capabilities? | High |
| Playlist management | M3U export only (for now) | Low |
| Artwork upload | When? Import only or edit later? | Low |
| Metadata editing | Full edit or just corrections? | Medium |
| Export formats | FLAC only? MP3? Both? | Medium |
| Multi-disc albums | How to handle? | Low |
| Compilation albums | Separate handling? | Low |

---

## 3. ARCHITECTURE DECISION

### Selected: API-First

```
+------------------+     +------------------+     +------------------+
|   CLI (Phase 1)  | --> |   API (Phase 1)  | <-- |   GUI (Phase 4)  |
+------------------+     +------------------+     +------------------+
                                  |
                                  v
                         +------------------+
                         |   Core Services  |
                         +------------------+
                                  |
              +-------------------+-------------------+
              |                   |                   |
              v                   v                   v
        +-----------+      +-----------+      +-----------+
        | Streamrip |      |   Beets   |      |   Plex    |
        | yt-dlp    |      | ExifTool  |      |   Lidarr  |
        +-----------+      +-----------+      +-----------+
```

### Why API-First?

| Benefit | Explanation |
|---------|-------------|
| Testable | curl/httpie before GUI |
| Scriptable | Automation, cron jobs |
| Debuggable | API logs show everything |
| Maintainable | GUI is thin layer |
| Future-proof | Mobile apps, integrations |

---

## 4. SYSTEM COMPONENTS

### 4.1 Services

| Service | Responsibility | Technology |
|---------|----------------|------------|
| API Server | HTTP endpoints, auth | FastAPI |
| Worker | Background jobs | Celery |
| Watcher | Watch folders | watchdog |
| WebSocket | Real-time updates | FastAPI WS |
| Database | Persistence | PostgreSQL |
| Cache/Queue | Jobs, pub/sub | Redis |

### 4.2 External Integrations

| Integration | Purpose | Protocol |
|-------------|---------|----------|
| Streamrip | Qobuz/Soundcloud downloads | CLI subprocess |
| yt-dlp | YouTube/Bandcamp/URL downloads | CLI subprocess |
| Beets | Metadata, organization | CLI subprocess |
| ExifTool | Quality extraction | CLI/Python lib |
| Lidarr | Automated downloads | REST API |
| Plex | Library scan trigger | REST API |
| TorrentLeech | Upload (admin) | REST API |
| Bandcamp Downloader | Purchase sync | CLI subprocess |

### 4.3 File System

```
/music/
+-- library/                    # MASTER (all music)
|   +-- Artist/
|       +-- Album (Year)/
|           +-- 01 - Track.flac
|           +-- cover.jpg
|
+-- users/                      # PER-USER (symlinks)
|   +-- username/
|       +-- Artist/ -> symlink
|
+-- downloads/                  # STAGING (temp)
|   +-- qobuz/
|   +-- lidarr/
|   +-- youtube/
|   +-- bandcamp/
|
+-- import/                     # MANUAL IMPORT
|   +-- pending/
|   +-- review/
|
+-- export/                     # EXPORT STAGING
```

---

## 5. PHASE BREAKDOWN

### PHASE 0: Foundation (Pre-Implementation)

**Goal:** Project setup, no code yet

| Task | Deliverable | Status |
|------|-------------|--------|
| Requirements complete | This blueprint | DONE |
| Integration docs | 14 docs in /docs | DONE |
| Design system | design-system.css | DONE |
| Docker compose draft | docker-compose.yml | DONE |
| Database schema draft | schema.sql | DONE |
| API contract draft | openapi.yaml | DONE |
| CLI contract draft | cli-spec.md | DONE |

**Exit Criteria:**
- [ ] All open questions answered (multi-disc, compilation, mobile app still open)
- [ ] docker-compose.yml reviewed
- [ ] Database schema approved
- [ ] API endpoints approved
- [ ] CLI commands approved

---

### PHASE 1: Core Backend

**Goal:** Working API + CLI, no GUI

**Duration Estimate:** Deferred to user

#### 1A: Database & Models

| Task | Details |
|------|---------|
| PostgreSQL setup | Docker, migrations |
| SQLAlchemy models | Users, Artists, Albums, Tracks |
| User library model | Hearts (album + track level) |
| Activity log | All actions tracked |
| Import history | Dupe protection |

#### 1B: Core Services

| Service | Functions |
|---------|-----------|
| LibraryService | CRUD artists/albums/tracks, search |
| UserLibraryService | Heart/unheart, list user library |
| QualityService | Extract quality, compare, decide |
| SymlinkService | Create/remove user library links |

#### 1C: API Endpoints

| Endpoint Group | Count |
|----------------|-------|
| /api/auth | 3 (login, logout, me) |
| /api/artists | 4 (list, get, search, delete) |
| /api/albums | 5 (list, get, tracks, delete, artwork) |
| /api/tracks | 3 (get, quality, delete) |
| /api/me/library | 6 (list, heart, unheart, export) |
| /api/admin/users | 4 (list, create, update, delete) |

#### 1D: CLI Wrapper

| Command Group | Commands |
|---------------|----------|
| barbossa library | list, search, info, delete |
| barbossa heart | add, remove, list |
| barbossa admin | users, rescan, integrity |

**Exit Criteria:**
- [ ] All API endpoints return correct data
- [ ] CLI commands work end-to-end
- [ ] Can create user, heart album, see in user library
- [ ] Unit tests pass
- [ ] Integration tests pass

---

### PHASE 2: Download Pipeline

**Goal:** All download sources working via CLI/API

#### 2A: Streamrip Integration

| Task | Details |
|------|---------|
| Search wrapper | qobuz album/artist/track/playlist |
| Download wrapper | Full album always |
| Config management | Quality, credentials |
| Progress tracking | Parse output |

#### 2B: Beets Import Pipeline

| Task | Details |
|------|---------|
| Auto-import trigger | On download complete |
| Metadata correction | MusicBrainz lookup |
| Path organization | Plex format |
| Artwork fetch | cover.jpg |
| Lyrics fetch | If available |

#### 2C: Quality & Dupe System

| Task | Details |
|------|---------|
| ExifTool extraction | Sample rate, bit depth |
| Dupe detection | Normalized artist/album/track |
| Quality comparison | Keep better version |
| Import history | Track everything |

#### 2D: Additional Sources

| Source | Implementation |
|--------|----------------|
| yt-dlp | URL paste handler |
| Lidarr | API request + watch folder |
| Bandcamp | Collection sync |

#### 2E: Plex Integration

| Task | Details |
|------|---------|
| Connection config | URL, token, section |
| Auto-scan | After import complete |
| Path-specific scan | Artist folder only |

**Exit Criteria:**
- [ ] `barbossa download search qobuz album "query"` works
- [ ] Downloaded album appears in library with correct metadata
- [ ] Plex scan triggered automatically
- [ ] Dupe detected and handled correctly
- [ ] Quality stored in database

---

### PHASE 3: Real-Time & Background

**Goal:** WebSocket updates, background workers

#### 3A: Celery Workers

| Queue | Tasks |
|-------|-------|
| downloads | Download from any source |
| imports | Beets import, quality extract |
| exports | User library export |
| maintenance | Rescan, integrity check |

#### 3B: WebSocket Server

| Event | Trigger |
|-------|---------|
| download:progress | Download percentage |
| download:complete | Download finished |
| import:complete | Album in library |
| library:updated | New content |
| toast | Notifications |

#### 3C: Watch Folders

| Folder | Action |
|--------|--------|
| /music/downloads/lidarr | Auto-import |
| /music/import/pending | Queue for review |

**Exit Criteria:**
- [ ] Download progress visible in real-time
- [ ] Toast appears when import complete
- [ ] Watch folders trigger imports
- [ ] No polling needed

---

### PHASE 4: GUI

**Goal:** React frontend consuming API

#### 4A: App Shell

| Component | Details |
|-----------|---------|
| Layout | Header, sidebar, content, player |
| Router | React Router, preserve player |
| Auth | Login, session |
| Theme | Light/dark toggle |

#### 4B: Library Pages

| Page | Components |
|------|------------|
| Master Library | Artist grid, album-card |
| User Library | Same, filtered |
| Artist Detail | Album list, heart |
| Album Detail | Track list, quality badges |

#### 4C: Downloads Page

| Component | Details |
|-----------|---------|
| Search | Auto-fallback from library to Qobuz, separate Lidarr search |
| Search results | Grid or list |
| URL paste | Universal handler |
| Queue | Active downloads |

#### 4D: Settings Page

| Section | Fields |
|---------|--------|
| Paths | Library, downloads, export |
| Users | CRUD table |
| Integrations | Qobuz, Lidarr, Plex |
| Quality | Default quality tier |

#### 4E: Supporting Features

| Feature | Details |
|---------|---------|
| Preview player | Persists across pages |
| Toasts | Real-time notifications |
| A-Z index | Quick navigation |
| Metadata editor | Modal for corrections |

**Exit Criteria:**
- [ ] All pages render correctly
- [ ] Heart/unheart works
- [ ] Downloads work from GUI
- [ ] Settings save correctly
- [ ] Player persists across navigation
- [ ] Dark mode works
- [ ] Mobile responsive

---

### PHASE 5: Admin & Polish

**Goal:** Admin features, edge cases, stability

#### 5A: Admin Features

| Feature | Details |
|---------|---------|
| TorrentLeech upload | Check exists, create torrent, upload |
| Bulk operations | Multi-select delete |
| Activity log view | Admin dashboard |
| System health | Disk space, service status |

#### 5B: Export System

| Feature | Details |
|---------|---------|
| Format selection | FLAC, MP3, or both |
| Destination | Local path or external |
| Progress | Background with notification |
| M3U playlist | Optional |

#### 5C: Edge Cases

| Case | Handling |
|------|----------|
| Multi-disc albums | Disc subfolder support |
| Compilations | Various Artists handling |
| Missing artwork | Placeholder or fetch |
| Failed imports | Review queue |
| Network failures | Retry with backoff |

#### 5D: Documentation

| Doc | Content |
|-----|---------|
| User guide | How to use Barbossa |
| Admin guide | Setup, maintenance |
| API reference | OpenAPI spec |
| Troubleshooting | Common issues |

**Exit Criteria:**
- [ ] TorrentLeech upload works
- [ ] Export creates valid files
- [ ] Edge cases handled gracefully
- [ ] Documentation complete
- [ ] No critical bugs

---

### PHASE 6: Deployment & Operations

**Goal:** Production-ready

| Task | Details | Status |
|------|---------|--------|
| Docker optimization | Multi-stage builds | DONE |
| Nginx/SSL | Reverse proxy with TLS | DONE |
| Backup strategy | Postgres backup scripts | DONE |
| Health checks | /health, /ready, /live | DONE |
| Logging | File rotation + console | DONE |
| Rate limiting | Nginx rate zones | DONE |

**Exit Criteria:**
- [x] One-command deployment (make prod-up)
- [x] Automated backups (backup.sh, restore.sh)
- [x] Health checks configured
- [x] Environment validation (scripts/validate_env.py)

---

## 6. DATA MODELS

### Core Entities

```
users
  id, username, password_hash, is_admin, created_at

artists
  id, name, normalized_name, path, artwork_path, created_at

albums
  id, artist_id, title, normalized_title, year, path,
  artwork_path, total_tracks, source, created_at

tracks
  id, album_id, title, normalized_title, track_number, disc_number,
  duration, path, sample_rate, bit_depth, bitrate, file_size,
  format, source, source_url, is_lossy, checksum, created_at

user_albums (hearts)
  user_id, album_id, added_at

user_tracks (track-level hearts)
  user_id, track_id, added_at

activity_log
  id, user_id, action, entity_type, entity_id, details, created_at

import_history
  id, artist_normalized, album_normalized, track_normalized,
  source, quality_score, checksum, import_date

downloads
  id, user_id, source, query, type, status, progress,
  error_message, started_at, completed_at

pending_review
  id, path, suggested_artist, suggested_album,
  confidence, status, reviewed_by, reviewed_at
```

---

## 7. API CONTRACT

### Authentication

```
POST /api/auth/login          # Get token
POST /api/auth/logout         # Invalidate token
GET  /api/auth/me             # Current user
```

### Library (Public)

```
GET  /api/artists             # List all (A-Z)
GET  /api/artists/:id         # Get artist
GET  /api/artists/:id/albums  # Artist's albums
GET  /api/albums              # List albums
GET  /api/albums/:id          # Get album
GET  /api/albums/:id/tracks   # Album tracks with quality
GET  /api/search?q=&type=     # Search library
```

### User Library

```
GET    /api/me/library              # User's hearted content
POST   /api/me/library/albums/:id   # Heart album
DELETE /api/me/library/albums/:id   # Unheart album
POST   /api/me/library/tracks/:id   # Heart track
DELETE /api/me/library/tracks/:id   # Unheart track
POST   /api/me/export               # Start export
```

### Downloads

```
GET  /api/downloads/search/qobuz?q=&type=   # Search Qobuz (artist/album/track/playlist)
GET  /api/downloads/search/lidarr?q=        # Search Lidarr
POST /api/downloads/qobuz                   # Download from Qobuz
POST /api/downloads/url                     # Download from URL
POST /api/downloads/lidarr/request          # Request via Lidarr
GET  /api/downloads/queue                   # Active downloads
DELETE /api/downloads/:id                   # Cancel download
```

### Admin

```
GET    /api/admin/users              # List users
POST   /api/admin/users              # Create user
PUT    /api/admin/users/:id          # Update user
DELETE /api/admin/users/:id          # Delete user
DELETE /api/albums/:id               # Delete from disk
POST   /api/admin/rescan             # Full library rescan
POST   /api/admin/integrity          # Verify checksums
GET    /api/admin/torrentleech/check # Check if exists
POST   /api/admin/torrentleech/upload/:album_id  # Upload
```

### WebSocket

```
WS /ws?token=xxx

Events (server -> client):
  download:progress  { id, progress, speed, eta }
  download:complete  { id, album_id }
  download:error     { id, error }
  import:complete    { album_id, artist, title }
  library:updated    { album_id, action }
  toast              { type, message }
```

---

## 8. CLI CONTRACT

```bash
# Library
barbossa library list [--user USER]
barbossa library search "query"
barbossa library info ALBUM_ID
barbossa library delete ALBUM_ID          # Admin

# User Library
barbossa heart ALBUM_ID [--user USER]
barbossa unheart ALBUM_ID [--user USER]
barbossa heart-track TRACK_ID [--user USER]

# Downloads
barbossa download search qobuz "query" --type album|artist|track
barbossa download search lidarr "query"
barbossa download url "https://..."
barbossa download queue
barbossa download cancel ID

# Import
barbossa import scan
barbossa import review
barbossa import approve ID
barbossa import reject ID

# Export
barbossa export --user USER --dest PATH --format flac|mp3|both

# Admin
barbossa admin users list
barbossa admin users add USERNAME [--admin]
barbossa admin users remove USERNAME
barbossa admin rescan
barbossa admin integrity

# TorrentLeech
barbossa tl check "Release.Name"
barbossa tl upload ALBUM_ID

# Integrations
barbossa lidarr status
barbossa lidarr request "Artist"
barbossa plex scan [--path PATH]
barbossa bandcamp sync
```

---

## 9. INTEGRATION MATRIX

| Source | Search | Download | Auto-Import | Quality |
|--------|--------|----------|-------------|---------|
| Qobuz (streamrip) | Yes | Yes | Yes | 24/192 max |
| Lidarr | Via Lidarr | Via Lidarr | Watch folder | Variable |
| YouTube (yt-dlp) | No* | URL paste | Yes | Lossy ~256k |
| Soundcloud (streamrip) | Yes | Yes | Yes | Lossy 256k |
| Bandcamp free (yt-dlp) | No* | URL paste | Yes | Lossy 128k |
| Bandcamp purchased | No | Collection sync | Yes | FLAC |
| Manual import | No | Watch folder | Review queue | Variable |

*Search not implemented; user provides URL

---

## 10. OPEN QUESTIONS

### Decisions

| # | Decision | Notes |
|---|----------|-------|
| 1 | Multi-disc handling | Support disc numbers and disc subfolders |
| 2 | Compilation handling | Avoid compilations; use artist "Soundtrack" for soundtrack releases |
| 3 | Mobile app | Not planned; web app only |

---

## 11. RISK ASSESSMENT

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Qobuz credential issues | Medium | High | Clear setup docs, validation |
| Streamrip API changes | Low | High | Pin version, monitor releases |
| Beets match failures | Medium | Medium | Review queue, manual override |
| Large library performance | Medium | Medium | Pagination, indexes, caching |
| Symlink permission issues | Medium | Low | Documentation, Docker volume setup |
| Plex path mapping | Medium | Low | Configuration, path translation |

---

## 12. ACCEPTANCE CRITERIA

### MVP (Phases 1-4 Complete)

- [ ] User can browse master library
- [ ] User can heart albums/tracks to personal library
- [ ] User can search and download from Qobuz
- [ ] Downloads auto-import with correct metadata
- [ ] Duplicates detected and handled
- [ ] Plex scan triggered on import
- [ ] Real-time progress updates
- [ ] Admin can manage users
- [ ] Settings persist across restarts
- [ ] Runs in Docker with one command

### Full Release (All Phases Complete)

- [ ] All MVP criteria
- [ ] TorrentLeech upload working
- [ ] Export to external drive working
- [ ] All download sources working
- [ ] Comprehensive documentation
- [ ] Monitoring and alerting
- [ ] Automated backups

---

## NEXT STEPS

1. **Answer Open Questions 1-3** before proceeding
2. **Create docker-compose.yml** draft
3. **Create database schema** (schema.sql)
4. **Create API spec** (openapi.yaml)
5. **Review and approve** Phase 0 deliverables
6. **Begin Phase 1** implementation

---

## APPENDIX: DOCUMENT INVENTORY

| Document | Location | Status |
|----------|----------|--------|
| Project overview | about.md | Current |
| Requirements | contracts.md | Current |
| Technical guide | techguide.md | Current |
| Changelog | changelog.md | v0.1.9 |
| Streamrip integration | docs/streamrip-integration.md | Complete |
| Beets integration | docs/beets-integration.md | Complete |
| ExifTool integration | docs/exiftool-integration.md | Complete |
| Lidarr integration | docs/lidarr-integration.md | Complete |
| yt-dlp integration | docs/ytdlp-integration.md | Complete |
| Plex integration | docs/plex-integration.md | Complete |
| Bandcamp integration | docs/bandcamp-integration.md | Complete |
| TorrentLeech integration | docs/torrentleech-integration.md | Complete |
| WebSocket implementation | docs/websocket-implementation.md | Complete |
| CI/CD pipeline | docs/cicd-pipeline.md | Complete |
| Monitoring/logging | docs/monitoring-logging.md | Complete |
| Rate limiting | docs/rate-limiting.md | Complete |
| Backup (rclone) | docs/rclone-backup.md | Complete |
| Playlist sync | docs/playlist-sync.md | Complete |
| Design system | frontend/src/styles/design-system.css | Complete |
| Blueprint | docs/BLUEPRINT.md | This file |
