# Barbossa Technical Guide

## Architecture

```
+-----------------------------------------------------------------------+
|                              Docker                                    |
+-----------------------------------------------------------------------+
|                                                                        |
|   +---------------+    +---------------+    +-------------+            |
|   |   Frontend    |    |    Backend    |    |   Worker    |            |
|   |  (React/Vue)  |--->|   (FastAPI)   |<---|  (Celery)   |            |
|   +---------------+    +-------+-------+    +------+------+            |
|                                |                    |                  |
|                          +-----+-----+        +-----+-----+            |
|                          | PostgreSQL|        |   Redis   |            |
|                          +-----------+        +-----------+            |
|                                                                        |
+-----------------------------------------------------------------------+
|   Volume: /music                                                       |
|   +-- artists/      (Master library - all music)                      |
|   +-- users/        (Per-user symlinked libraries)                    |
|   +-- downloads/    (Temp: qobuz/, lidarr/)                           |
|   +-- import/       (pending/, review/, rejected/)                    |
|   +-- database/     (Database backups)                                |
|   +-- export/       (User export staging)                             |
+-----------------------------------------------------------------------+
            |                           |
            v                           v
      Plex Media Server          External Services
      (auto-scans library)       +-- Lidarr API
            |                    +-- Qobuz (streamrip)
            v                    +-- YouTube (yt-dlp)
         Plexamp                 +-- TorrentLeech API
      (actual listening)
```

## Docker Compose

```yaml
version: '3.8'

services:
  barbossa:
    build: ./backend
    ports:
      - "8080:8080"
    volumes:
      - /path/to/music:/music
      - ./config:/config
    environment:
      - DATABASE_URL=postgresql://barbossa:password@db/barbossa
      - REDIS_URL=redis://redis:6379
      - QOBUZ_EMAIL=${QOBUZ_EMAIL}
      - QOBUZ_PASSWORD=${QOBUZ_PASSWORD}
      - LIDARR_URL=${LIDARR_URL}
      - LIDARR_API_KEY=${LIDARR_API_KEY}
      - PLEX_URL=${PLEX_URL}
      - PLEX_TOKEN=${PLEX_TOKEN}
    depends_on:
      - db
      - redis

  worker:
    build: ./backend
    command: celery -A app.worker worker -l info -Q downloads,imports,maintenance
    volumes:
      - /path/to/music:/music
      - ./config:/config
    environment:
      - DATABASE_URL=postgresql://barbossa:password@db/barbossa
      - REDIS_URL=redis://redis:6379
      - QOBUZ_EMAIL=${QOBUZ_EMAIL}
      - QOBUZ_PASSWORD=${QOBUZ_PASSWORD}
      - LIDARR_URL=${LIDARR_URL}
      - LIDARR_API_KEY=${LIDARR_API_KEY}
    depends_on:
      - db
      - redis

  beat:
    build: ./backend
    command: celery -A app.worker beat -l info
    environment:
      - DATABASE_URL=postgresql://barbossa:password@db/barbossa
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  watcher:
    build: ./backend
    command: python -m app.watcher
    volumes:
      - /path/to/music:/music
    environment:
      - DATABASE_URL=postgresql://barbossa:password@db/barbossa
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"

  db:
    image: postgres:15-alpine
    volumes:
      - barbossa_db:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=barbossa
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=barbossa

  redis:
    image: redis:7-alpine

volumes:
  barbossa_db:
```

---

## API Endpoints

### Library

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/artists` | List all artists (A-Z) |
| GET | `/api/artists/{id}` | Get artist details |
| GET | `/api/artists/{id}/albums` | Get artist's albums |
| GET | `/api/albums` | List albums (optional artist_id, letter filter) |
| GET | `/api/albums/{id}` | Get album details |
| GET | `/api/albums/{id}/tracks` | Get album tracks with quality info |
| GET | `/api/search?q=&type=` | Search library (type: artist/album/track) |
| GET | `/api/search/unified?q=&type=` | Unified search with Qobuz fallback |
| DELETE | `/api/albums/{id}` | Delete album from disk |

### User Library

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/me/library` | Get current user's hearted albums |
| GET | `/api/me/library/tracks` | Get current user's hearted tracks |
| POST | `/api/me/library/albums/{id}` | Heart album (create symlinks) |
| DELETE | `/api/me/library/albums/{id}` | Unheart album (remove symlinks) |
| POST | `/api/me/library/tracks/{id}` | Heart individual track |
| DELETE | `/api/me/library/tracks/{id}` | Unheart individual track |
| POST | `/api/me/library/artists/{id}` | Heart artist (adds all albums to library) |
| DELETE | `/api/me/library/artists/{id}` | Unheart artist (removes all albums from library) |
| GET | `/api/me/activity` | Get user's activity log |
| POST | `/api/me/export` | Start library export |
| GET | `/api/me/export/{id}` | Get export status |

**Auto-Heart Behavior:**
- When all tracks on an album are individually hearted, the album is automatically hearted
- This creates album-level symlinks and marks the album as hearted in the UI
- Works for albums with any number of tracks (including single-track albums)

### Unified Search

The `/api/search/unified` endpoint provides a single search interface with external fallback.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query (min 1 char) |
| `type` | string | No | Search type: `artist`, `album`, `track` (default: `album`). NO `playlist` allowed. |
| `include_external` | bool | No | Search Qobuz if local results empty (default: `false`) |
| `limit` | int | No | Max results 1-50 (default: `20`) |

**Response:**
```json
{
  "query": "Beatles",
  "type": "album",
  "local": {
    "count": 2,
    "albums": [...],
    "artists": [],
    "tracks": []
  },
  "external": null
}
```

When `include_external=true` and local count is 0, `external` contains Qobuz results:
```json
{
  "external": {
    "source": "qobuz",
    "count": 10,
    "items": [...],
    "error": null
  }
}
```

### Downloads

Downloads are a temporary staging area only. Imported albums land in the master library.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/downloads/search/qobuz?q=&type=` | Search Qobuz (type: artist/album/track/playlist) |
| GET | `/api/downloads/search/lidarr?q=` | Search Lidarr |
| POST | `/api/downloads/qobuz` | Start Qobuz download (optional `search_type` for auto-heart rule) |
| POST | `/api/downloads/url` | Start URL download (YouTube, Bandcamp, Soundcloud) |
| POST | `/api/downloads/lidarr/request` | Request via Lidarr |
| GET | `/api/downloads/queue` | Get download queue |
| DELETE | `/api/downloads/{id}` | Cancel download |

### Qobuz Catalog Browsing

Browse Qobuz catalog with artwork before downloading. Requires authentication.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/qobuz/search?q=&type=&limit=` | Search Qobuz catalog (type: album/artist/track) |
| GET | `/api/qobuz/artist/{id}?sort=` | Get artist discography (sort: year/title) |
| GET | `/api/qobuz/album/{id}` | Get album with track listing |

**Search Response:**
```json
{
  "query": "Pink Floyd",
  "type": "album",
  "count": 2,
  "albums": [{
    "id": "u5jzer5t2bmqb",
    "title": "Wish You Were Here",
    "artist_name": "Pink Floyd",
    "artwork_url": "https://static.qobuz.com/.../600.jpg",
    "hires": true,
    "maximum_bit_depth": 24,
    "maximum_sampling_rate": 192.0,
    "in_library": false
  }]
}
```

### Import

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/import/pending` | List pending imports |
| GET | `/api/import/review` | List items needing review |
| POST | `/api/import/review/{id}/approve` | Approve with suggestion |
| POST | `/api/import/review/{id}/manual` | Manual metadata entry |
| POST | `/api/import/review/{id}/reject` | Reject import |
| POST | `/api/import/trigger` | Manually trigger import scan |

### Streaming (Preview)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tracks/{track_id}/stream` | Stream audio file (accepts `?token=` query param) |
| GET | `/api/albums/{album_id}/artwork` | Get album artwork |
| PUT | `/api/albums/{album_id}/artwork` | Update album artwork |
| DELETE | `/api/albums/{album_id}/artwork` | Restore original album artwork |
| GET | `/api/artists/{artist_id}/artwork` | Get artist artwork (falls back to first album cover) |
| PUT | `/api/artists/{artist_id}/artwork` | Upload custom artist artwork |
| DELETE | `/api/artists/{artist_id}/artwork` | Restore original artist artwork |
| POST | `/api/artists/{artist_id}/artwork/fetch` | Fetch artist artwork from Qobuz |
| POST | `/api/artwork/artists/fetch-all` | Batch fetch missing artist artwork from Qobuz |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/users` | List users |
| POST | `/api/admin/users` | Create user |
| PUT | `/api/admin/users/{id}` | Update user |
| DELETE | `/api/admin/users/{id}` | Delete user |
| GET | `/api/settings` | Get settings |
| PUT | `/api/settings` | Update settings (music_library, qobuz_quality, etc.) |
| GET | `/api/settings/browse?path=` | Browse filesystem directories |
| GET | `/api/admin/torrentleech/check?q=` | Check if album exists on TL |
| POST | `/api/admin/torrentleech/upload/{album_id}` | Upload album to TL |
| POST | `/api/admin/rescan` | Rescan library |
| GET | `/api/admin/activity` | Get all activity logs |
| GET | `/api/admin/health` | Library health report |
| POST | `/api/admin/integrity/verify` | Run integrity check |
| GET | `/api/admin/backup/history` | Backup history |
| POST | `/api/admin/backup/trigger` | Trigger manual backup |

### Lidarr Integration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/lidarr/status` | Check Lidarr connection |
| GET | `/api/lidarr/artists` | List monitored artists |
| POST | `/api/lidarr/artists` | Add artist to Lidarr |
| GET | `/api/lidarr/queue` | Get Lidarr download queue |
| POST | `/api/lidarr/search` | Trigger Lidarr search |

### WebSocket

Connect: `ws://localhost:8080/ws?token=<jwt>`

| Event | Direction | Description |
|-------|-----------|-------------|
| `heartbeat` | Server->Client | Connection keepalive (every 30s) |
| `download:progress` | Server->Client | Download progress update |
| `download:complete` | Server->Client | Download finished |
| `download:error` | Server->Client | Download failed |
| `import:complete` | Server->Client | Import finished |
| `import:review` | Server->Client | Item needs review |
| `activity` | Server->Client | User activity (hearts, new albums) |
| `notification` | Server->Client | User-specific notification |
| `library:updated` | Server->Client | Library change (add/update/delete) |
| `ping` | Client->Server | Request pong response |
| `pong` | Server->Client | Pong response |
| `subscribe` | Client->Server | Subscribe to channel |
| `unsubscribe` | Client->Server | Unsubscribe from channel |

Channels: `downloads`, `activity`, `library`

---

## Core Services

### 1. Download Service (Multi-Source)

Notes:
- Always download full album even if user requests a single track.
- Auto-heart only when `search_type` is `track`.

```python
from celery import Celery
from enum import Enum

class DownloadSource(Enum):
    QOBUZ = "qobuz"
    LIDARR = "lidarr"
    YOUTUBE = "youtube"

celery = Celery('barbossa')

@celery.task(queue='downloads')
def download_from_qobuz(url: str, user_id: int):
    """Download from Qobuz via streamrip."""
    import subprocess

    result = subprocess.run(
        ["rip", "--quality", "4", "url", url],
        capture_output=True,
        cwd="/music/downloads/qobuz"
    )

    if result.returncode != 0:
        raise Exception(f"Streamrip failed: {result.stderr}")

    downloaded_path = find_newest_folder("/music/downloads/qobuz")
    return process_import(downloaded_path, DownloadSource.QOBUZ, user_id)

@celery.task(queue='downloads')
def download_from_youtube(url: str, user_id: int, confirm_lossy: bool = False):
    """Download from YouTube via yt-dlp."""
    if not confirm_lossy:
        raise Exception("User must confirm lossy download")

    import subprocess

    result = subprocess.run([
        "yt-dlp", "-x",
        "--audio-format", "flac",
        "--audio-quality", "0",
        "-o", "/music/downloads/youtube/%(artist)s/%(album)s/%(track_number)02d - %(title)s.%(ext)s",
        url
    ], capture_output=True)

    if result.returncode != 0:
        raise Exception(f"yt-dlp failed: {result.stderr}")

    downloaded_path = find_newest_folder("/music/downloads/youtube")
    return process_import(downloaded_path, DownloadSource.YOUTUBE, user_id, is_lossy=True)

@celery.task(queue='downloads')
def request_from_lidarr(artist_name: str, artist_mbid: str, user_id: int):
    """Add artist to Lidarr for monitoring."""
    import httpx

    response = httpx.post(
        f"{LIDARR_URL}/api/v1/artist",
        headers={"X-Api-Key": LIDARR_API_KEY},
        json={
            "foreignArtistId": artist_mbid,
            "monitored": True,
            "qualityProfileId": 1,
            "rootFolderPath": "/music"
        }
    )

    if response.status_code not in (200, 201):
        raise Exception(f"Lidarr request failed: {response.text}")

    # Trigger search
    artist_id = response.json()["id"]
    httpx.post(
        f"{LIDARR_URL}/api/v1/command",
        headers={"X-Api-Key": LIDARR_API_KEY},
        json={"name": "ArtistSearch", "artistId": artist_id}
    )

    log_activity(user_id, 'lidarr_request', 'artist', artist_id, {'name': artist_name})
    return {"status": "requested", "artist_id": artist_id}
```

### 2. Import Service

```python
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class ImportResult:
    success: bool
    album_id: Optional[int]
    needs_review: bool
    review_id: Optional[int]
    message: str

@celery.task(queue='imports')
def process_import(
    path: Path,
    source: DownloadSource,
    user_id: int,
    is_lossy: bool = False
) -> ImportResult:
    """Process downloaded content through import pipeline."""

    # 1. Run beets import
    result = subprocess.run(
        ["beet", "import", "-q", str(path)],
        capture_output=True
    )

    # Check if beets matched
    if "No matching release found" in result.stderr.decode():
        # Move to review queue
        review_path = Path("/music/import/review") / path.name
        shutil.move(path, review_path)

        review_id = create_pending_review(
            path=str(review_path),
            beets_output=result.stderr.decode(),
            source=source.value
        )

        notify_websocket('import:review', {'review_id': review_id})
        return ImportResult(False, None, True, review_id, "Needs manual review")

    # 2. Find imported album in library
    album_path = find_imported_album(path)

    # 3. Extract quality and generate checksums
    tracks = []
    for file in album_path.glob("*.flac"):
        quality = quality_service.extract(file)
        checksum = generate_checksum(file)
        tracks.append({
            'path': file,
            'quality': quality,
            'checksum': checksum
        })

    # 4. Check for duplicates and compare quality
    for track in tracks:
        existing = dupe_service.find_duplicate(
            artist=album_path.parent.name,
            album=album_path.name,
            track=track['path'].stem
        )

        if existing:
            if dupe_service.should_replace(existing, track['quality']):
                # Replace with better quality
                replace_track(existing, track)
                log_activity(user_id, 'quality_upgrade', 'track', existing.id, {
                    'old_quality': f"{existing.sample_rate}/{existing.bit_depth}",
                    'new_quality': f"{track['quality'].sample_rate}/{track['quality'].bit_depth}"
                })
            else:
                # Keep existing, skip this track
                continue

    # 5. Index in database
    album_id = index_album(
        album_path,
        tracks,
        source=source.value,
        is_lossy=is_lossy,
        imported_by=user_id
    )

    # 6. Trigger Plex scan
    notify_plex(album_path)

    # 7. Log activity
    log_activity(user_id, 'import', 'album', album_id, {'source': source.value})

    # 8. Notify via WebSocket
    notify_websocket('import:complete', {'album_id': album_id})

    return ImportResult(True, album_id, False, None, "Import successful")
```

### Multi-Disc Handling

- Use `disc_number` on tracks.
- Allow disc subfolders (CD1, Disc 2) during import and export.
- Preserve disc order in UI and export playlists.

### Compilation Handling

- Avoid compilation handling in the library model.
- Use artist name `Soundtrack` for soundtrack releases.

### 3. Library Service

```python
from pathlib import Path
import shutil

class LibraryService:
    def __init__(self, master_path: str, users_path: str):
        self.master = Path(master_path)
        self.users = Path(users_path)

    def add_to_user_library(self, username: str, album_path: Path):
        """Create symlinks for album in user's library."""
        relative = album_path.relative_to(self.master)
        user_album = self.users / username / relative

        user_album.mkdir(parents=True, exist_ok=True)

        for file in album_path.iterdir():
            dest = user_album / file.name
            self._create_link(file, dest)

    def remove_from_user_library(self, username: str, album_path: Path):
        """Remove symlinks from user's library."""
        relative = album_path.relative_to(self.master)
        user_album = self.users / username / relative

        if user_album.exists():
            shutil.rmtree(user_album)
            self._cleanup_empty_parents(user_album.parent)

    def delete_from_master(self, album_path: Path):
        """Delete album from disk entirely."""
        # First remove from all user libraries
        for user_dir in self.users.iterdir():
            relative = album_path.relative_to(self.master)
            user_album = user_dir / relative
            if user_album.exists():
                shutil.rmtree(user_album)

        # Then delete from master
        shutil.rmtree(album_path)
        self._cleanup_empty_parents(album_path.parent)

    def _create_link(self, source: Path, dest: Path):
        """Create hardlink if possible, fallback to symlink."""
        try:
            dest.hardlink_to(source)
        except OSError:
            dest.symlink_to(source)

    def _cleanup_empty_parents(self, path: Path):
        """Remove empty parent directories."""
        while path != self.master and path != self.users:
            if not any(path.iterdir()):
                path.rmdir()
                path = path.parent
            else:
                break
```

### 4. Quality Service

```python
from exiftool import ExifToolHelper
from dataclasses import dataclass
import hashlib

@dataclass
class TrackQuality:
    sample_rate: int
    bit_depth: int
    bitrate: int
    file_size: int
    format: str

class QualityService:
    def extract(self, file_path: Path) -> TrackQuality:
        """Extract audio quality metadata."""
        with ExifToolHelper() as et:
            data = et.get_tags(
                [str(file_path)],
                tags=["SampleRate", "BitsPerSample", "AudioBitrate", "FileSize", "FileType"]
            )[0]

        return TrackQuality(
            sample_rate=data.get("FLAC:SampleRate") or data.get("MPEG:SampleRate") or 44100,
            bit_depth=data.get("FLAC:BitsPerSample") or 16,
            bitrate=data.get("MPEG:AudioBitrate") or 0,
            file_size=data.get("File:FileSize") or 0,
            format=data.get("File:FileType") or "FLAC"
        )

    def is_better_quality(self, new: TrackQuality, existing: TrackQuality) -> bool:
        """Check if new file is higher quality."""
        # Priority: sample_rate > bit_depth > file_size
        if new.sample_rate > existing.sample_rate:
            return True
        if new.sample_rate == existing.sample_rate:
            if new.bit_depth > existing.bit_depth:
                return True
            if new.bit_depth == existing.bit_depth:
                if new.file_size > existing.file_size:
                    return True
        return False

    def quality_score(self, quality: TrackQuality) -> int:
        """Compute numeric quality score for comparison."""
        return (quality.sample_rate * 100) + quality.bit_depth

def generate_checksum(file_path: Path) -> str:
    """Generate SHA-256 checksum for integrity verification."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()
```

### 5. Export Service

Playlist management is limited to M3U export only for now.

```python
import subprocess
from pathlib import Path

@celery.task(queue='exports')
def export_user_library(
    user_id: int,
    destination: str,
    format: str = 'flac',  # 'flac', 'mp3', 'both'
    include_artwork: bool = True,
    include_lyrics: bool = True
):
    """Export user's library to external destination."""
    user = db.get_user(user_id)
    user_library = Path(f"/music/users/{user.username}")
    dest = Path(destination)

    total_albums = count_albums(user_library)
    processed = 0

    for artist_dir in user_library.iterdir():
        if not artist_dir.is_dir():
            continue

        for album_dir in artist_dir.iterdir():
            if not album_dir.is_dir():
                continue

            # Create destination structure
            dest_album = dest / artist_dir.name / album_dir.name
            dest_album.mkdir(parents=True, exist_ok=True)

            for file in album_dir.iterdir():
                # Resolve symlink to actual file
                source = file.resolve()

                if file.suffix.lower() in ('.flac', '.mp3', '.m4a'):
                    if format == 'flac' or format == 'both':
                        shutil.copy2(source, dest_album / file.name)

                    if format == 'mp3' or format == 'both':
                        mp3_name = file.stem + '.mp3'
                        convert_to_mp3(source, dest_album / mp3_name)

                elif file.name == 'cover.jpg' and include_artwork:
                    shutil.copy2(source, dest_album / file.name)

                elif file.suffix == '.lrc' and include_lyrics:
                    shutil.copy2(source, dest_album / file.name)

            processed += 1
            notify_websocket('export:progress', {
                'user_id': user_id,
                'progress': int((processed / total_albums) * 100)
            })

    # Generate M3U playlist
    generate_m3u(dest, user.username)

    # Generate manifest
    generate_manifest(dest, user_id)

    log_activity(user_id, 'export', 'library', None, {
        'destination': destination,
        'format': format,
        'album_count': total_albums
    })

    notify_websocket('export:complete', {'user_id': user_id})

def convert_to_mp3(source: Path, dest: Path):
    """Convert audio file to 320kbps MP3."""
    subprocess.run([
        'ffmpeg', '-i', str(source),
        '-codec:a', 'libmp3lame',
        '-b:a', '320k',
        '-y', str(dest)
    ], check=True, capture_output=True)
```

### 6. Plex Integration

```python
import httpx

class PlexService:
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        self.section_id = None  # Cached

    async def get_music_section_id(self) -> int:
        """Get the music library section ID."""
        if self.section_id:
            return self.section_id

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.url}/library/sections",
                params={"X-Plex-Token": self.token}
            )

            # Parse XML response to find Music section
            # ... parsing logic ...
            self.section_id = music_section_id
            return self.section_id

    async def scan_path(self, path: str):
        """Trigger Plex to scan a specific path."""
        section_id = await self.get_music_section_id()

        async with httpx.AsyncClient() as client:
            await client.get(
                f"{self.url}/library/sections/{section_id}/refresh",
                params={
                    "path": path,
                    "X-Plex-Token": self.token
                }
            )

    async def scan_library(self):
        """Trigger full library scan."""
        section_id = await self.get_music_section_id()

        async with httpx.AsyncClient() as client:
            await client.get(
                f"{self.url}/library/sections/{section_id}/refresh",
                params={"X-Plex-Token": self.token}
            )

async def notify_plex(album_path: Path):
    """Notify Plex of new content."""
    plex = PlexService(PLEX_URL, PLEX_TOKEN)
    await plex.scan_path(str(album_path.parent))  # Scan artist folder
```

### 7. Watch Folder Service

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

class ImportWatcher(FileSystemEventHandler):
    def __init__(self):
        self.pending_path = Path("/music/import/pending")
        self.debounce = {}  # Prevent duplicate triggers

    def on_created(self, event):
        if event.is_directory:
            return

        # Debounce: wait for folder to be fully copied
        folder = Path(event.src_path).parent
        self.debounce[str(folder)] = time.time()

    def on_modified(self, event):
        # Same debounce logic
        pass

    def check_ready_imports(self):
        """Check for folders ready to import (no changes for 30 seconds)."""
        now = time.time()
        ready = []

        for folder, last_change in list(self.debounce.items()):
            if now - last_change > 30:  # 30 second quiet period
                ready.append(folder)
                del self.debounce[folder]

        return ready

def run_watcher():
    """Main watcher process."""
    handler = ImportWatcher()
    observer = Observer()
    observer.schedule(handler, "/music/import/pending", recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(10)

            for folder in handler.check_ready_imports():
                # Trigger import task
                process_import.delay(
                    Path(folder),
                    DownloadSource.IMPORT,
                    user_id=1  # System user for auto-imports
                )
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
```

### 8. Lidarr Service

```python
import httpx
from typing import List, Optional

class LidarrService:
    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.headers = {"X-Api-Key": api_key}

    async def check_connection(self) -> bool:
        """Test Lidarr connection."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/api/v1/system/status",
                    headers=self.headers,
                    timeout=5
                )
                return response.status_code == 200
        except:
            return False

    async def get_monitored_artists(self) -> List[dict]:
        """Get all monitored artists."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.url}/api/v1/artist",
                headers=self.headers
            )
            return response.json()

    async def add_artist(self, mbid: str, name: str) -> dict:
        """Add artist to Lidarr for monitoring."""
        async with httpx.AsyncClient() as client:
            # First search for artist
            search = await client.get(
                f"{self.url}/api/v1/artist/lookup",
                headers=self.headers,
                params={"term": f"lidarr:{mbid}"}
            )

            if not search.json():
                raise Exception(f"Artist not found: {name}")

            artist_data = search.json()[0]
            artist_data["monitored"] = True
            artist_data["qualityProfileId"] = 1
            artist_data["metadataProfileId"] = 1
            artist_data["rootFolderPath"] = "/music/downloads/lidarr"

            response = await client.post(
                f"{self.url}/api/v1/artist",
                headers=self.headers,
                json=artist_data
            )

            return response.json()

    async def trigger_search(self, artist_id: int):
        """Trigger search for artist's music."""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.url}/api/v1/command",
                headers=self.headers,
                json={"name": "ArtistSearch", "artistId": artist_id}
            )

    async def get_queue(self) -> List[dict]:
        """Get current download queue."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.url}/api/v1/queue",
                headers=self.headers
            )
            return response.json().get("records", [])

    async def get_history(self, limit: int = 50) -> List[dict]:
        """Get download history."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.url}/api/v1/history",
                headers=self.headers,
                params={"pageSize": limit, "sortKey": "date", "sortDirection": "descending"}
            )
            return response.json().get("records", [])
```

---

## Frontend Components

### Library Navigation Components

**ArtistCard.jsx** - Artist display card
- Square artwork with rounded corners (reuses album-card CSS)
- Artist name only (no album count per spec)
- Artwork placeholder shows first letter of name (on image load error)
- Heart icon (bottom-left): adds/removes all albums by artist from library
- Trash icon (top-right, 1s delay): deletes artist and all albums from disk
- Pencil icon (top-left, on hover): opens file picker to upload custom artwork
- Artwork fetched from `/api/artists/{id}/artwork` (falls back to first album cover)

**ArtistGrid.jsx** - Grid of artist cards
- Responsive grid layout (reuses album-grid CSS)
- Empty state when no artists found
- onClick handler for drilling into artist

**Library.jsx** - Master Library page (Artist -> Album -> Track flow)
- Default: Shows all Artists with A-Z filter on right
- Click artist: Shows that artist's Albums with back button
- Click album: Opens AlbumModal with Tracks
- Uses `getArtists()` and `getArtistAlbums()` API calls

**UserLibrary.jsx** - User Library page (same flow as Master)
- Toggle between Albums and Tracks views
- Albums view: Groups hearted albums by artist, shows Artists -> Albums -> Tracks drill-down
- Tracks view: Lists all individually hearted tracks with album/artist info
- A-Z filter and search bar for filtering artists (albums view only)

### Layout Components

**Sidebar.jsx** - Main navigation with integrated search
- Search input at top (above navigation)
- Type selector: Albums / Artists / Tracks (NO Playlist option)
- Navigate to `/search?q=X&type=Y` on submit
- Escape clears input
- Theme toggle in footer
- Navigation order: My Library, Master Library, Downloads, Settings

**Layout.jsx** - Page wrapper
- Sidebar + main content area + Player + ToastContainer
- No separate header component (page titles in content area)

### Search Page (Search.jsx)

**Auto-Cascade Search Flow:**
1. User searches -> Local search runs automatically
2. If local empty -> Qobuz search triggers automatically (no click needed)
3. If both empty -> Fallback modal with Lidarr/YouTube/URL options

**UI States:**

1. **No Query** - "Enter a search term in the sidebar"
2. **Loading Local** - Spinner with "Searching library..."
3. **Local Results Found** - AlbumGrid/ArtistList/TrackList + "Search more" button at bottom
4. **Loading Qobuz** - Progress: "No results in library" (crossed out) + "Searching Qobuz..."
5. **Qobuz Results** - Results grid + "Try other sources" button
6. **No Results Anywhere** - Empty state with "Try other sources" button

**"Search more" Modal (opens from any results page):**
- Search Qobuz (shown when user has local results - quality upgrade path)
- Request via Lidarr (automated monitoring)
- Search YouTube (lossy warning)
- Paste URL (redirect to Downloads)

### Preview Player (persists across pages)

Uses [react-h5-audio-player](https://github.com/lhz516/react-h5-audio-player).

```bash
npm install react-h5-audio-player zustand
```

```jsx
// components/PreviewPlayer.jsx
import AudioPlayer from 'react-h5-audio-player';
import 'react-h5-audio-player/lib/styles.css';
import { useAudioStore } from '../stores/audio';

export function PreviewPlayer() {
  const { currentTrack, clearTrack } = useAudioStore();

  if (!currentTrack) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-700">
      <div className="flex items-center gap-4 px-4">
        <img
          src={`/api/albums/${currentTrack.albumId}/artwork`}
          alt={currentTrack.album}
          className="w-14 h-14 rounded"
        />
        <div className="min-w-[200px]">
          <div className="text-white font-medium truncate">{currentTrack.title}</div>
          <div className="text-gray-400 text-sm truncate">
            {currentTrack.artist}
            {currentTrack.isLossy && <span className="ml-2 text-yellow-500">(lossy)</span>}
          </div>
        </div>

        <div className="flex-1">
          <AudioPlayer
            src={`/api/tracks/${currentTrack.id}/stream`}
            showJumpControls={false}
            layout="horizontal-reverse"
            className="barbossa-player"
            onEnded={() => clearTrack()}
          />
        </div>

        <button onClick={clearTrack} className="text-gray-400 hover:text-white p-2">
          X
        </button>
      </div>
    </div>
  );
}
```

### Source Badge Component

```jsx
// components/SourceBadge.jsx
const SOURCE_COLORS = {
  qobuz: 'bg-blue-500',
  lidarr: 'bg-green-500',
  youtube: 'bg-red-500',
  import: 'bg-gray-500'
};

const SOURCE_LABELS = {
  qobuz: 'Qobuz',
  lidarr: 'Lidarr',
  youtube: 'YT',
  import: 'Import'
};

export function SourceBadge({ source, quality, isLossy }) {
  return (
    <div className="flex items-center gap-1">
      <span className={`px-1.5 py-0.5 rounded text-xs text-white ${SOURCE_COLORS[source]}`}>
        {SOURCE_LABELS[source]}
      </span>
      {quality && (
        <span className={`text-xs ${isLossy ? 'text-yellow-500' : 'text-gray-400'}`}>
          {quality}
        </span>
      )}
    </div>
  );
}
```

### Download Source Selector

```jsx
// components/DownloadSourceSelector.jsx
export function DownloadSourceSelector({ album, onSelect }) {
  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <p className="text-white mb-3">"{album.title}" not in library</p>

      <div className="space-y-2">
        <button
          onClick={() => onSelect('qobuz')}
          className="w-full flex justify-between items-center p-3 bg-blue-600 hover:bg-blue-700 rounded"
        >
          <span>Download from Qobuz</span>
          <span className="text-blue-200">24/192 max</span>
        </button>

        <button
          onClick={() => onSelect('lidarr')}
          className="w-full flex justify-between items-center p-3 bg-green-600 hover:bg-green-700 rounded"
        >
          <span>Request via Lidarr</span>
          <span className="text-green-200">automated</span>
        </button>

        <button
          onClick={() => onSelect('youtube')}
          className="w-full flex justify-between items-center p-3 bg-gray-600 hover:bg-gray-700 rounded"
        >
          <span>Search YouTube</span>
          <span className="text-yellow-400">lossy</span>
        </button>
      </div>
    </div>
  );
}
```

---

## Configuration

`/config/barbossa.yml`:
```yaml
server:
  host: 0.0.0.0
  port: 8080

paths:
  master_library: /music/artists
  user_libraries: /music/users
  downloads: /music/downloads
  import_pending: /music/import/pending
  import_review: /music/import/review
  export_staging: /music/export

# Source: Qobuz (Primary)
qobuz:
  enabled: true
  quality: 4  # 0-4, 4 is max (24/192)

# Source: Lidarr (External)
lidarr:
  enabled: true
  url: http://lidarr.local:8686
  api_key: ""
  auto_request: true  # Auto-add missing to Lidarr
  fill_gaps: true     # Use for incomplete albums
  import_path: /music/downloads/lidarr  # Optional: watch folder

# Source: YouTube (Fallback)
youtube:
  enabled: true
  require_confirmation: true
  mark_as_lossy: true

# Import settings
import:
  watch_folder: true
  auto_import_confidence: 85  # Below this -> review queue
  generate_checksums: true

# Beets configuration
beets:
  config: /config/beets/config.yaml

# Plex integration
plex:
  enabled: true
  url: http://plex:32400
  token: ""
  auto_scan: true

# TorrentLeech (Admin only)
torrentleech:
  enabled: false
  announce_key: ""

# Export settings
export:
  formats:
    - flac
    - mp3_320
  include_artwork: true
  include_lyrics: true

# Backup settings
backup:
  enabled: true
  destinations:
    - type: local
      path: /backup/music
  schedule: weekly  # daily, weekly, monthly
  verify_after: true

# Quality comparison
quality:
  prefer_highest: true
  allow_mixed_sources: true

# Activity logging
activity_log:
  enabled: true
  retention_days: 365
```

---

## CLI Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f barbossa
docker-compose logs -f worker

# User management
docker-compose exec barbossa barbossa admin create-user <username>
docker-compose exec barbossa barbossa admin list-users
docker-compose exec barbossa barbossa admin delete-user <username> [-f|--force]

# Import album from folder
docker-compose exec barbossa barbossa admin import <path> [OPTIONS]
#   --artist, -a    Override artist name
#   --album, -A     Override album name
#   --year, -y      Override year
#   --copy, -c      Copy files instead of moving
#   --force, -f     Import even if duplicate detected

# Rescan library
docker-compose exec barbossa barbossa admin rescan [OPTIONS]
#   --path, -p      Specific path to scan (defaults to library root)
#   --dry-run, -n   Show what would be done without making changes

# Database initialization
docker-compose exec barbossa barbossa admin db-init
docker-compose exec barbossa barbossa admin seed [--user admin] [--pass password]

# Check for duplicates
docker-compose exec barbossa python -m app.cli dupes --dry-run

# Run integrity check
docker-compose exec barbossa python -m app.cli integrity --verify

# Trigger backup
docker-compose exec barbossa python -m app.cli backup --destination /backup

# Export user library
docker-compose exec barbossa python -m app.cli export --user dad --format both --dest /mnt/external

# Check Lidarr connection
docker-compose exec barbossa python -m app.cli lidarr --status

# Process pending reviews
docker-compose exec barbossa python -m app.cli review --list

# Rebuild all symlinks from database (use if symlinks are missing)
docker-compose exec barbossa python -m app.cli.main library rebuild-symlinks [OPTIONS]
#   --user, -u      Rebuild for specific user only
#   --dry-run       Preview changes without modifying

# Fix existing symlinks (converts absolute to relative paths)
docker-compose exec barbossa python -m app.cli.main library fix-symlinks [OPTIONS]
#   --user, -u      Fix specific user only
#   --dry-run       Preview changes without modifying
```

---

## Dependencies

### Backend (requirements.txt)
```
fastapi>=0.100.0
uvicorn>=0.23.0
sqlalchemy>=2.0.0
alembic>=1.11.0
celery>=5.3.0
redis>=4.6.0
httpx>=0.24.0
python-multipart>=0.0.6
pydantic>=2.0.0
PyExifTool>=0.5.0
watchdog>=3.0.0
websockets>=11.0.0
passlib>=1.7.4
python-jose>=3.3.0
```

### System Dependencies (Dockerfile)
```dockerfile
RUN apt-get update && apt-get install -y \
    ffmpeg \
    exiftool \
    mktorrent \
    mediainfo \
    && rm -rf /var/lib/apt/lists/*

# Install streamrip
RUN pip install streamrip

# Install yt-dlp
RUN pip install yt-dlp

# Install beets with plugins
RUN pip install beets pyacoustid requests pylast
```
