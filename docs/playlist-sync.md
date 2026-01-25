# Playlist Sync & Management Guide

## Overview

Barbossa supports playlist import from external services and M3U export. Direct sync with Spotify/Apple Music is not implemented due to API restrictions, but workarounds exist via Last.fm and IPTC converters.

## Supported Playlist Formats

| Format | Import | Export | Notes |
|--------|--------|--------|-------|
| M3U/M3U8 | Yes | Yes | Primary format |
| Last.fm | Yes | No | Via Streamrip |
| Spotify | Partial | No | Via Last.fm conversion |
| Apple Music | Partial | No | Via Last.fm conversion |
| YouTube Music | Yes | No | Via yt-dlp |
| Soundcloud | Yes | No | Via URL |

## Import Methods

### 1. Last.fm Playlists (Recommended for Spotify/Apple)

Streamrip supports Last.fm URLs directly. Users can use third-party services to sync their Spotify/Apple Music playlists to Last.fm.

```bash
# Download Last.fm playlist
rip lastfm "https://www.last.fm/user/username/playlists/12345678"

# Download user's loved tracks
rip lastfm "https://www.last.fm/user/username/loved"

# Download top tracks
rip lastfm "https://www.last.fm/user/username/library/tracks?date_preset=LAST_365_DAYS"
```

### Workflow: Spotify to Barbossa

```
1. User creates Last.fm account
2. User connects Spotify to Last.fm (scrobbling)
   - OR uses third-party converter like Soundiiz, TuneMyMusic
3. User shares Last.fm playlist URL
4. Barbossa downloads via Streamrip
5. Tracks matched to Qobuz catalog
```

### 2. YouTube Music Playlists

yt-dlp handles YouTube Music playlist URLs.

```bash
# Download YouTube Music playlist
yt-dlp -x --audio-format flac --audio-quality 0 \
  "https://music.youtube.com/playlist?list=PLxxxxxxx"
```

**Limitations:**
- Quality is lossy (~256kbps max)
- Metadata may need manual correction
- Large playlists limited to 50 tracks per request

### 3. M3U Import

Users can drop M3U files in the import watch folder or upload via UI.

```
# Example M3U format
#EXTM3U
#EXTINF:234,Pink Floyd - Comfortably Numb
/music/artists/Pink Floyd/The Wall (1979)/06 - Comfortably Numb.flac
#EXTINF:412,Led Zeppelin - Stairway to Heaven
/music/artists/Led Zeppelin/Led Zeppelin IV (1971)/04 - Stairway to Heaven.flac
```

## Export Methods

### M3U Export

```python
# app/services/playlist_export.py
from pathlib import Path
from typing import List
from app.models import Track

def generate_m3u(
    tracks: List[Track],
    output_path: Path,
    relative_paths: bool = True,
    base_path: Path = None
) -> Path:
    """Generate M3U playlist file."""

    lines = ['#EXTM3U']

    for track in tracks:
        # Duration and display name
        duration = track.duration or -1
        display = f"{track.artist_name} - {track.title}"
        lines.append(f"#EXTINF:{duration},{display}")

        # File path
        if relative_paths and base_path:
            path = Path(track.path).relative_to(base_path)
        else:
            path = track.path

        lines.append(str(path))

    output_path.write_text('\n'.join(lines), encoding='utf-8')
    return output_path

def generate_m3u8(tracks: List[Track], output_path: Path) -> Path:
    """Generate M3U8 (UTF-8) playlist."""
    # Same as M3U but ensures UTF-8 encoding
    return generate_m3u(tracks, output_path)
```

### Export with User Library

```python
@celery.task(queue='exports')
def export_user_library(
    user_id: int,
    destination: str,
    format: str = 'flac',
    include_playlists: bool = True
):
    """Export user library with playlists."""

    user = db.get_user(user_id)
    dest = Path(destination)

    # Export music files...
    # (existing logic)

    if include_playlists:
        # Generate "All Tracks" playlist
        all_tracks = db.get_user_tracks(user_id)
        generate_m3u(
            all_tracks,
            dest / f"{user.username}_all_tracks.m3u",
            relative_paths=True,
            base_path=dest
        )

        # Generate per-artist playlists
        artists = db.get_user_artists(user_id)
        playlists_dir = dest / 'Playlists'
        playlists_dir.mkdir(exist_ok=True)

        for artist in artists:
            tracks = db.get_user_tracks_by_artist(user_id, artist.id)
            generate_m3u(
                tracks,
                playlists_dir / f"{artist.name}.m3u",
                relative_paths=True,
                base_path=dest
            )
```

## Playlist Database Schema

```sql
-- User playlists (for future local playlist management)
CREATE TABLE playlists (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    source VARCHAR(50),  -- 'manual', 'lastfm', 'import'
    source_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE playlist_tracks (
    playlist_id INT REFERENCES playlists(id) ON DELETE CASCADE,
    track_id INT REFERENCES tracks(id) ON DELETE CASCADE,
    position INT NOT NULL,
    added_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (playlist_id, track_id)
);

-- Indexes
CREATE INDEX idx_playlist_user ON playlists(user_id);
CREATE INDEX idx_playlist_tracks_position ON playlist_tracks(playlist_id, position);
```

## API Endpoints

```python
# app/api/playlists.py
from fastapi import APIRouter, Depends, UploadFile, File
from app.auth import get_current_user

router = APIRouter()

@router.post("/playlists/import/lastfm")
async def import_lastfm_playlist(
    url: str,
    user = Depends(get_current_user)
):
    """Import playlist from Last.fm URL."""
    # Validate URL
    if 'last.fm' not in url:
        raise HTTPException(400, "Invalid Last.fm URL")

    # Queue download task
    task = download_lastfm_playlist.delay(url, user.id)

    return {
        "task_id": task.id,
        "message": "Playlist import started"
    }

@router.post("/playlists/import/m3u")
async def import_m3u_playlist(
    name: str,
    file: UploadFile = File(...),
    user = Depends(get_current_user)
):
    """Import M3U playlist file."""
    content = await file.read()

    # Parse M3U
    tracks = parse_m3u(content.decode('utf-8'))

    # Match to library
    matched = []
    unmatched = []

    for entry in tracks:
        track = db.find_track_by_path_or_metadata(entry)
        if track:
            matched.append(track)
        else:
            unmatched.append(entry)

    # Create playlist
    playlist = db.create_playlist(
        user_id=user.id,
        name=name,
        source='import'
    )

    for i, track in enumerate(matched):
        db.add_track_to_playlist(playlist.id, track.id, position=i)

    return {
        "playlist_id": playlist.id,
        "matched": len(matched),
        "unmatched": len(unmatched),
        "unmatched_entries": unmatched[:10]  # Show first 10
    }

@router.get("/playlists/{playlist_id}/export")
async def export_playlist(
    playlist_id: int,
    format: str = 'm3u',
    user = Depends(get_current_user)
):
    """Export playlist as M3U file."""
    playlist = db.get_playlist(playlist_id)

    if not playlist or (playlist.user_id != user.id and not playlist.is_public):
        raise HTTPException(404, "Playlist not found")

    tracks = db.get_playlist_tracks(playlist_id)

    # Generate M3U
    content = generate_m3u_content(tracks)

    return Response(
        content=content,
        media_type='audio/x-mpegurl',
        headers={
            'Content-Disposition': f'attachment; filename="{playlist.name}.m3u"'
        }
    )
```

## Third-Party Conversion Services

Since direct Spotify/Apple Music API access is restricted, recommend these services to users:

### Spotify to Last.fm

1. **Last.fm Scrobbler** (official)
   - Enable Spotify scrobbling in Last.fm settings
   - Builds listening history over time

2. **Soundiiz** (soundiiz.com)
   - One-time playlist transfer
   - Spotify -> Last.fm (or vice versa)
   - Free tier: 1 playlist at a time

3. **TuneMyMusic** (tunemymusic.com)
   - Similar to Soundiiz
   - Supports more platforms

### Apple Music to Last.fm

1. **Last.fm iOS Scrobbler**
   - Scrobbles Apple Music plays

2. **Marvis Pro** (iOS)
   - Third-party Apple Music player
   - Built-in scrobbling

## Limitations & Notes

### Why No Direct Spotify/Apple Sync?

1. **Spotify API** - Requires OAuth, user authentication, and app approval. Streaming/downloading is prohibited by ToS.

2. **Apple Music API** - Similar restrictions. MusicKit requires Apple Developer account.

3. **Legal** - Direct download from these services violates terms of service.

### Recommended Workflow

```
User's Spotify Playlist
        |
        v
[Third-party converter]
        |
        v
    Last.fm Playlist
        |
        v
  Barbossa (via Streamrip)
        |
        v
    Qobuz Search & Download
        |
        v
    Local Library (FLAC)
```

This approach:
- Uses legitimate streaming (Qobuz subscription)
- Gets higher quality than Spotify (24-bit vs 320kbps)
- Creates owned local copies
- Works with any playlist source

## Future Considerations

### Potential Enhancements

1. **Playlist Matching Service**
   - User provides Spotify playlist URL
   - Barbossa parses track list (no streaming)
   - Searches Qobuz for each track
   - Shows match results before download

2. **Subsonic API Compatibility**
   - Implement Subsonic/Airsonic API
   - Allows use with Subsonic-compatible apps
   - Would enable playlist sync with those apps

3. **Plex Playlist Sync**
   - Two-way sync with Plex playlists
   - Read Plex playlists via API
   - Push Barbossa playlists to Plex

### Implementation Complexity

| Feature | Complexity | Notes |
|---------|------------|-------|
| Plex playlist sync | Medium | Plex API is well-documented |
| Subsonic API | High | Full API implementation needed |
| Spotify URL parsing | Medium | Just parse, don't stream |
| Native playlist UI | Medium | Standard CRUD operations |
