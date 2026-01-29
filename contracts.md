# Barbossa - Contracts & Specifications

## Pages

### 1. Master Library
- Shows ALL music in the centralized library
- All users can browse
- Same interface as User Library

### 2. User Library
- Shows only music the user has "hearted"
- Backed by symlinks (hard links if available) to master library
- Path: `/music/users/{username}/`

### 3. Downloads (Temporary Staging)
Downloads are a temporary staging area only. Imported albums land in the master library.

Two input methods: **Search** and **URL paste**

#### Search (Simple - 3 Options)
| Button | Source | Notes |
|--------|--------|-------|
| Search Library | Local database | Check what you have |
| Search Qobuz | Streamrip | High quality (24/192) |
| Search Lidarr | External Lidarr | Automated/rare content |

Search types (user must select): Artist / Track / Album / Playlist
Do NOT auto-search playlists from header search.

#### URL Paste (Universal)
Paste any URL - yt-dlp handles automatically:
- YouTube / YouTube Music
- Soundcloud
- Bandcamp (free tracks only)
- Mixcloud, Archive.org, 1800+ sites

For Bandcamp purchases: Settings > Bandcamp Sync

#### Download Rules
- Always downloads full album (even if user selects single track)
- Does NOT auto-add to user library unless user downloads a single song
- Show quality warning for lossy sources (YouTube, Soundcloud, etc.)

#### Download Queue UI
- Active downloads shown with progress bar, speed, and ETA
- Download count badge shown in sidebar nav (pending/downloading/importing count)
- Failed downloads shown in separate section with:
  - Error message/reason
  - Timestamp of failure
  - Retry button (restarts download)
  - Dismiss button (removes from queue)

### 4. Import
- Watch folder for manual imports
- Review queue for unidentified content
- Supports: CD rips, Bandcamp, other purchases, existing collections

### 5. Settings
- Music Library Location
- User Management (add/remove/edit users)
- Source Settings:
  - Qobuz: quality (0-4), credentials
  - Lidarr: URL, API key, auto-request toggle
  - YouTube: enabled/disabled, quality warning
- Download Folders:
  - Watch folder
  - Torrent folder
  - Usenet folder
  - Barbossa download location
- Backup Settings: destinations, schedule
- Plex Integration: URL, token

---

## Interface Specifications

### Album Grid View (Master & User Library)
- Square album artwork with rounded corners
- Artist name only (no album count)
- Clean, minimal design

### Artist/Albums Page
| Element | Position | Behavior |
|---------|----------|----------|
| Heart icon | Bottom-left of album | Click adds/removes album from user library |
| Trash icon | Top-right of album | Appears on hover (1 second delay), deletes from disk |
| Edit icon | Top-right of artwork | Appears on hover, opens file picker for artwork |
| A-Z nav | Right side of page | Jump to letter |

- Trash requires warning modal + confirm button
- **Artist cards follow same pattern**: Heart (bottom-left) adds/removes ALL albums by artist, Trash (top-right, 1s delay) deletes artist and all albums
- Source badges shown per-track in album modal, not on album cards

### Album/Song Page
- Each track row: `[Heart] [Play/Pause] [Track #] [Title] [Source Badge] [Quality] [Duration]`
- Play button always visible; shows Pause icon when that track is playing
- Heart adds/removes individual song from user library (auto-hearts album when all tracks hearted)
- Album art displayed prominently
- Quality indicator: 24/192, 16/44.1, or "lossy"
- Mixed-source albums show per-track source

### Search (Sidebar)
- Search input in sidebar (below navigation, above footer)
- Force user to select search type: Artist / Track / Album
- Do NOT include playlist option in sidebar search
- Download count badge shown next to "Downloads" nav link when active
- Search local library first
- If no local results, show external source options:
  - [Search Qobuz] - 24/192 max
  - [Request Lidarr] - automated
  - [Search YouTube] - lossy warning
  - [Paste URL] - redirect to Downloads

### Download Source Selection
When content not in local library:
```
+------------------------------------------+
|  "Album Name" not in library             |
|                                          |
|  [Download from Qobuz]      (24/192)     |
|  [Request via Lidarr]       (automated)  |
|  [Search YouTube]           (lossy)      |
+------------------------------------------+
```

### Preview Player
- Simple HTML5 audio player at bottom of screen
- Click track to preview (check if it works)
- Persists across page navigation
- NOT for serious listening (use Plexamp for that)

### Notifications
- Toast notifications for errors/successes
- Works even when user is on different page
- Non-blocking
- Types: download complete, import complete, quality upgrade, error

### Pending Review Queue

Downloads that need manual review (low confidence match, missing metadata) show inline on the Downloads page with action buttons:

```
Downloads > Download Queue
+-------------------------------------------------------------+
| [qobuz] https://www.qobuz.com/us-en/album/...              |
|    pending_review - Needs manual review                     |
|                                        [Approve] [Dismiss]  |
+-------------------------------------------------------------+
```

- **Approve** - Accepts the suggested match and imports to library
- **Dismiss** - Removes the download record from the queue

---

## Backend Requirements

### Library Structure
```
/Volumes/media/library/music/   # Host path (mounted as /music in container)
├── artists/                    # Master library (all music)
│   └── Artist Name/
│       └── Album Name (Year)/
│           ├── cover.jpg
│           ├── 01 - Track Title.flac
│           └── 02 - Track Title.flac
├── users/
│   ├── dad/                    # Dad's library (symlinks)
│   ├── mom/                    # Mom's library (symlinks)
│   └── kid/                    # Kid's library (symlinks)
├── downloads/                  # Temp download location
│   ├── qobuz/                  # Streamrip output
│   └── lidarr/                 # Lidarr completed (if local)
├── import/
│   ├── pending/                # Drop files here
│   ├── review/                 # Beets couldn't identify
│   └── rejected/               # Duplicates, corrupt files
├── database/                   # Database backups
│   └── db_YYYYMMDD_HHMMSS.sql.gz
└── export/                     # User export staging
```

### Download Source Priority

| Priority | Source | Quality | Method | When to Use |
|----------|--------|---------|--------|-------------|
| 1 | Qobuz (streamrip) | 24/192 max | Search | Always try first |
| 2 | Lidarr (Usenet/Torrent) | Variable | Search | Gaps, automation, rare |
| 3 | Bandcamp (purchases) | FLAC | Sync | Owned albums |
| 4 | Manual Import | Variable | Watch folder | CD rips, other purchases |
| 5 | Soundcloud | 256kbps max | URL paste | DJ mixes, remixes |
| 6 | YouTube (yt-dlp) | ~256kbps | URL paste | Last resort only |
| 7 | Bandcamp (free) | 128kbps | URL paste | Preview/discovery |

**Rule:** Lossless sources (1-4) always preferred over lossy (5-7).

### Import Pipeline
```
1. Source downloads to staging area
2. Beets processes: metadata, artwork, lyrics, Plex naming
3. ExifTool extracts: sample_rate, bit_depth, file_size
4. Checksum generated for integrity
5. Dupe check against database (quality comparison)
6. If better quality or new: move to /music/artists/
7. Index in Barbossa database with source tracking
8. Plex API: trigger scan of artist folder
9. Activity log: record import event
```

### Incomplete Album Handling
```
Album requested: 12 tracks
Qobuz has: 10 tracks
         |
         v
Download 10 from Qobuz (best quality)
         |
         v
Mark album as INCOMPLETE in DB
missing_tracks: ["Track 11", "Track 12"]
         |
         v
Auto-search Lidarr for full album
         |
    +----+----+
    |         |
  Found    Not Found
    |         |
    v         v
Compare    Search yt-dlp
quality    for specific tracks
    |         |
    v         v
Keep best  Mark as "lossy source"
per-track  in track metadata
         |
         v
Album status: COMPLETE (mixed sources)
```

### Multi-Disc Handling
- Support disc numbers in track metadata
- Allow disc subfolders (e.g., CD1, Disc 2)
- Preserve disc order in UI and export

### Duplicate Detection
- Track by: artist (normalized), album (normalized), track title
- Normalize: remove (Deluxe), (Remaster), [Explicit], etc.
- If dupe found, compare quality:
  - Higher sample_rate wins
  - If equal, higher bit_depth wins
  - If equal, larger file_size wins
  - If equal, keep existing (preserve source priority)
- Handles deluxe edition variants
- Log all replacements in activity log

### Database Schema
```sql
-- Users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Music catalog (mirrors filesystem)
CREATE TABLE artists (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    path VARCHAR(512)
);

CREATE TABLE albums (
    id SERIAL PRIMARY KEY,
    artist_id INT REFERENCES artists(id),
    title VARCHAR(255) NOT NULL,
    normalized_title VARCHAR(255) NOT NULL,
    year INT,
    path VARCHAR(512),
    artwork_path VARCHAR(512),
    total_tracks INT,
    available_tracks INT,
    status VARCHAR(20) DEFAULT 'complete',  -- complete, incomplete, pending
    missing_tracks JSONB,  -- ["Track 11", "Track 12"]
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE tracks (
    id SERIAL PRIMARY KEY,
    album_id INT REFERENCES albums(id),
    title VARCHAR(255) NOT NULL,
    normalized_title VARCHAR(255) NOT NULL,
    track_number INT,
    duration INT,  -- seconds
    path VARCHAR(512),
    -- Quality data
    sample_rate INT,
    bit_depth INT,
    bitrate INT,
    file_size BIGINT,
    format VARCHAR(10),
    -- Source tracking
    source VARCHAR(20) NOT NULL,  -- qobuz, lidarr, youtube, import
    source_url TEXT,
    source_quality VARCHAR(50),  -- "24/192 FLAC", "YouTube 256kbps"
    is_lossy BOOLEAN DEFAULT FALSE,
    -- Integrity
    checksum VARCHAR(64),  -- SHA-256
    checksum_verified_at TIMESTAMP,
    -- Timestamps
    imported_at TIMESTAMP DEFAULT NOW(),
    imported_by_user_id INT REFERENCES users(id)
);

-- Per-user libraries
CREATE TABLE user_library (
    user_id INT REFERENCES users(id),
    album_id INT REFERENCES albums(id),
    added_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, album_id)
);

CREATE TABLE user_tracks (
    user_id INT REFERENCES users(id),
    track_id INT REFERENCES tracks(id),
    added_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, track_id)
);

-- Import history (dupe protection)
CREATE TABLE import_history (
    id SERIAL PRIMARY KEY,
    artist_normalized VARCHAR(255),
    album_normalized VARCHAR(255),
    track_normalized VARCHAR(255),
    source VARCHAR(20),
    quality_score INT,  -- Computed: sample_rate * 100 + bit_depth
    import_date TIMESTAMP DEFAULT NOW()
);

-- Download queue
CREATE TABLE downloads (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    source VARCHAR(20) NOT NULL,  -- qobuz, lidarr, youtube
    source_url TEXT,
    search_query TEXT,
    search_type VARCHAR(20),  -- artist, album, track
    status VARCHAR(20) DEFAULT 'pending',  -- pending, downloading, importing, complete, failed, cancelled, pending_review
    progress INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Activity log
CREATE TABLE activity_log (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    action VARCHAR(50) NOT NULL,  -- import, heart, unheart, delete, export, quality_upgrade
    entity_type VARCHAR(20),  -- album, track, artist
    entity_id INT,
    details JSONB,  -- Additional context
    created_at TIMESTAMP DEFAULT NOW()
);

-- Pending review queue
CREATE TABLE pending_review (
    id SERIAL PRIMARY KEY,
    path VARCHAR(512) NOT NULL,
    suggested_artist VARCHAR(255),
    suggested_album VARCHAR(255),
    beets_confidence FLOAT,
    track_count INT,
    quality_info JSONB,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, approved, rejected
    reviewed_by INT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Backup history
CREATE TABLE backup_history (
    id SERIAL PRIMARY KEY,
    destination VARCHAR(255),
    status VARCHAR(20),  -- running, complete, failed
    files_backed_up INT,
    total_size BIGINT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

### Symlink Management
```python
def add_album_to_user_library(user_id: int, album_id: int):
    """Heart an album - create symlinks for all tracks."""
    album = db.get_album(album_id)
    user = db.get_user(user_id)

    source = Path(album.path)
    dest = Path(f"/music/users/{user.username}") / source.relative_to("/music/artists")

    dest.mkdir(parents=True, exist_ok=True)

    for file in source.iterdir():
        link_path = dest / file.name
        try:
            link_path.hardlink_to(file)  # Prefer hardlink
        except OSError:
            link_path.symlink_to(file)   # Fallback to symlink

    db.add_to_user_library(user_id, album_id)
    log_activity(user_id, 'heart', 'album', album_id)

def remove_album_from_user_library(user_id: int, album_id: int):
    """Unheart an album - remove symlinks."""
    album = db.get_album(album_id)
    user = db.get_user(user_id)

    dest = Path(f"/music/users/{user.username}") / Path(album.path).relative_to("/music/artists")

    if dest.exists():
        shutil.rmtree(dest)
    cleanup_empty_dirs(dest.parent)

    db.remove_from_user_library(user_id, album_id)
    log_activity(user_id, 'unheart', 'album', album_id)
```

### Metadata Editing
- **Any user** can edit track/album metadata (not just admins)
- Users can fix metadata on their own downloads before import
- Users can edit metadata on tracks in their library
- Changes apply to master library files
- Symlinks automatically reflect changes
- Log changes in activity log with user attribution

### Custom Artwork
- Upload custom album artwork on import (when auto-detection fails)
- Replace existing artwork if wrong
- Accepted formats: JPG, PNG (converted to JPG for storage)
- Minimum size: 500x500, recommended: 1400x1400
- Square aspect ratio enforced (auto-crop if needed)

#### UI Locations
| Where | When |
|-------|------|
| Import review queue | Album not identified, artwork missing |
| Album page | Click artwork > "Replace Artwork" |
| Pending downloads | Before import completes |

#### Workflow
1. User uploads image
2. System crops to square (center crop)
3. Resizes to 1400x1400 if larger
4. Saves as `cover.jpg` in album folder
5. Embeds in all track files (via beets)
6. Plex scan picks up new artwork

---

## Export Feature

Playlist management is limited to M3U export only for now.

### Compilation Handling
- Avoid compilation handling in the library model
- For soundtrack releases, use artist name "Soundtrack"

### User Library Export
```
Settings > My Library > Export

Export Format:
  [x] FLAC (full quality, larger files)
  [ ] MP3 320kbps (portable, smaller files)
  [ ] Both formats

Include:
  [x] Album artwork
  [x] Lyrics files (.lrc)
  [x] Playlists (M3U)

Destination:
  [/path/to/external/drive________]

[Start Export]
```

### Export Process
1. Copy files (not symlinks) from user's hearted albums
2. Convert to MP3 if requested (ffmpeg)
3. Preserve folder structure: Artist/Album (Year)/
4. Include cover.jpg, *.lrc files
5. Generate M3U playlist of all tracks
6. Generate JSON manifest with metadata

---

## Additional Features

### TorrentLeech Upload
- Upload button: top-right of album art
- Appears on hover (1 second delay)
- Before upload:
  - Search TorrentLeech API to check if exists
  - Show warning if already exists
- Upload process:
  - Generate NFO from MediaInfo
  - Create .torrent with mktorrent
  - Upload via TorrentLeech API

### User Management
- Add/remove family members
- View user library stats
- View activity log per user

### Library Health
- Integrity verification (checksum)
- Incomplete album report
- Lossy content report
- Duplicate detection report
- Storage usage per user

### Backup Management
- Configure destinations (local, NAS, rclone)
- Set schedule (daily, weekly, monthly)
- View backup history
- Trigger manual backup
- Verify backup integrity

---

## Real-Time Updates

Use WebSocket for:
- Download progress
- Download complete notifications
- Import complete notifications
- Quality upgrade notifications
- Library updates (new albums)
- Toast notifications

---

## Lidarr Integration

### Connection
- External Lidarr instance (separate system)
- Connect via API (URL + API key)
- Barbossa does NOT run Lidarr

### Features
| Feature | Description |
|---------|-------------|
| Request artist | Add artist to Lidarr's wanted list |
| Fill gaps | Auto-request missing tracks from incomplete albums |
| Import completed | Watch Lidarr's download folder or pull via API |
| Status sync | Show Lidarr download status in Barbossa |

### API Endpoints Used
```
GET  /api/v1/artist              # List monitored artists
POST /api/v1/artist              # Add artist to monitor
GET  /api/v1/album               # List albums
POST /api/v1/command             # Trigger search
GET  /api/v1/queue               # Download queue
GET  /api/v1/history             # Completed downloads
```

---

## YouTube (yt-dlp) Integration

### Use Cases
- Live recordings not on Qobuz
- Unreleased tracks
- Remixes and bootlegs
- Region-locked content

### Restrictions
- Always show quality warning before download
- Mark tracks as "lossy source" in database
- Never prefer over Qobuz/Lidarr for same content
- Require user confirmation

### Quality Settings
```bash
yt-dlp -x --audio-format flac --audio-quality 0 \
  -o "%(artist)s/%(album)s/%(track_number)02d - %(title)s.%(ext)s" \
  URL
```

Note: Output is lossy even if converted to FLAC (source is compressed)

---

## Resolved Research Questions

| Question | Answer | Reference |
|----------|--------|-----------|
| Streamrip search best practices | Force user to select type (artist/track/album) | `docs/streamrip-integration.md` |
| TorrentLeech pre-check API | Yes - `/api/torrentsearch` returns 0 or 1 | `docs/torrentleech-integration.md` |
| Dedupe detection | Streamrip has own DB, Barbossa adds quality comparison | `docs/exiftool-integration.md` |
| Hardlinks vs symlinks | Try hardlink first, fallback to symlink | Python `os.link()` |
| Plex naming format | `$albumartist/$album ($year)/$track - $title` | `docs/beets-integration.md` |
| Plex auto-scan API | `GET /library/sections/{id}/refresh?path=` | Plex API |
| Lidarr integration | External API, not embedded | `docs/lidarr-integration.md` |
| yt-dlp quality | ~256kbps max, always lossy | `docs/ytdlp-integration.md` |
| Beets quality comparison | Only bitrate tiebreak, not sample_rate | Barbossa handles |

---

## External Tool Integration

| Tool | Purpose | Docs |
|------|---------|------|
| Streamrip | Download from Qobuz + Soundcloud | `docs/streamrip-integration.md` |
| Beets | Metadata, naming, artwork, lyrics | `docs/beets-integration.md` |
| ExifTool | Extract audio quality data | `docs/exiftool-integration.md` |
| TorrentLeech | Admin upload feature | `docs/torrentleech-integration.md` |
| Lidarr | Automated downloads, gap filling | `docs/lidarr-integration.md` |
| yt-dlp | Universal URL handler (YouTube, Soundcloud, Bandcamp free, etc.) | `docs/ytdlp-integration.md` |
| bandcamp-collection-downloader | Bandcamp purchase sync | `docs/bandcamp-integration.md` |
| Plex | Library scan trigger | `docs/plex-integration.md` |
| FFmpeg | Audio conversion, thumbnail crop | System dependency |
| rclone | Cloud backup | `docs/rclone-backup.md` |

## Operational Documentation

| Topic | Purpose | Docs |
|-------|---------|------|
| WebSocket | Real-time updates implementation | `docs/websocket-implementation.md` |
| CI/CD | GitHub Actions, deployment | `docs/cicd-pipeline.md` |
| Monitoring | Prometheus, Grafana, ELK | `docs/monitoring-logging.md` |
| Rate Limiting | API protection | `docs/rate-limiting.md` |
| Playlists | Import/export, sync workarounds | `docs/playlist-sync.md` |

---

## File Organization

```
barbossa/
├── about.md
├── contracts.md
├── techguide.md
├── changelog.md
├── docker-compose.yml             # All 7 services, health-gated
├── .env.example                   # Template for deployment
├── docs/
│   ├── streamrip-integration.md   # Qobuz + Soundcloud search
│   ├── beets-integration.md       # Import pipeline
│   ├── exiftool-integration.md    # Quality extraction
│   ├── torrentleech-integration.md # Admin upload
│   ├── lidarr-integration.md      # Automated downloads
│   ├── ytdlp-integration.md       # Universal URL handler
│   ├── bandcamp-integration.md    # Bandcamp purchases + free
│   └── plex-integration.md        # Library scan API
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh              # DB verification + startup
│   ├── .dockerignore
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/                   # Database migrations
│   ├── config/                    # Beets config, etc.
│   ├── db/
│   │   ├── schema.sql             # Full schema reference
│   │   └── init/                  # Postgres first-run init scripts
│   │       └── 001_schema.sql
│   └── app/
│       ├── main.py
│       ├── api/
│       ├── services/
│       └── models/
├── frontend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── nginx.conf                 # Reverse proxy to API
│   ├── package.json
│   └── src/
└── config/
    └── default.yml
```
