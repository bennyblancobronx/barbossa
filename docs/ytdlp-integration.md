# yt-dlp Integration

yt-dlp is the **universal URL handler** for the Downloads page. When users paste a URL (not using search), yt-dlp processes it.

## Supported Sites (URL Paste)

yt-dlp supports 1800+ sites. Key music sources:

| Source | URL Example | Quality |
|--------|-------------|---------|
| YouTube | `youtube.com/watch?v=...` | ~256kbps (lossy) |
| YouTube Music | `music.youtube.com/watch?v=...` | ~256kbps (lossy, better metadata) |
| Soundcloud | `soundcloud.com/artist/track` | 128-256kbps (lossy) |
| Bandcamp | `artist.bandcamp.com/track/...` | 128kbps (free only) |
| Vimeo | `vimeo.com/123456` | Variable |
| Mixcloud | `mixcloud.com/...` | 320kbps (lossy) |
| Archive.org | `archive.org/details/...` | Variable |

**Note:** Bandcamp purchases require separate tool (see bandcamp-integration.md).

## Architecture

```
Downloads Page
|
+-- Search Box --> Qobuz (streamrip) / Lidarr
|
+-- URL Field --> yt-dlp handles ALL URLs
                  - YouTube, Soundcloud, Bandcamp, etc.
                  - Auto-detects site
                  - Extracts best audio
```

## Important Limitations

**YouTube audio is ALWAYS lossy**, regardless of output format:
- Source: ~256kbps Opus or AAC
- Converting to FLAC does NOT improve quality
- Always marked as `is_lossy: true` in database

**Use only when:**
- Track not available on Qobuz
- Lidarr cannot find it
- User explicitly confirms lossy download

## Configuration

```yaml
youtube:
  enabled: true
  require_confirmation: true  # Always warn user
  mark_as_lossy: true         # Flag in database
  search_limit: 20            # Max results to show
  prefer_youtube_music: true  # Use music.youtube.com URLs
```

## Installation

yt-dlp is installed in the Docker container:

```dockerfile
RUN pip install yt-dlp

# FFmpeg required for audio extraction and thumbnail processing
RUN apt-get update && apt-get install -y ffmpeg
```

---

## Optimized Music Download Command

```bash
yt-dlp \
  # Audio extraction
  -f bestaudio \
  -x \
  --audio-format flac \
  --audio-quality 0 \

  # Thumbnail: crop to square (removes 16:9 letterbox)
  --embed-thumbnail \
  --convert-thumbnails png \
  --ppa "ThumbnailsConvertor+ffmpeg_o:-c:v png -vf crop=\"'if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'\"" \

  # Metadata embedding with fallbacks
  --embed-metadata \
  --parse-metadata "playlist_index:%(track_number)s" \
  --parse-metadata "%(album,playlist_title)s:%(meta_album)s" \
  --parse-metadata "%(artist,channel,uploader)s:%(meta_artist)s" \
  --parse-metadata "%(release_year,upload_date>%Y)s:%(meta_date)s" \

  # Clear unwanted fields
  --parse-metadata ":(?P<synopsis>)" \
  --parse-metadata ":(?P<description>)" \

  # Save metadata JSON for inspection
  --write-info-json \

  # Output template with fallbacks
  -o "%(artist,channel)s/%(album,playlist_title)s/%(track_number,playlist_index|00)02d - %(title)s.%(ext)s" \

  # Misc
  --no-overwrites \
  --windows-filenames \

  URL
```

---

## Metadata Parsing Reference

### Key Fields and Fallbacks

| Field | Primary Source | Fallback 1 | Fallback 2 |
|-------|---------------|------------|------------|
| `artist` | `artist` | `channel` | `uploader` |
| `album` | `album` | `playlist_title` | "Unknown Album" |
| `track_number` | `track_number` | `playlist_index` | - |
| `title` | `track` | `title` | - |
| `year` | `release_year` | `upload_date` (first 4 chars) | - |

### Parse-Metadata Syntax

```bash
# Basic: copy field
--parse-metadata "uploader:%(artist)s"

# With fallback chain
--parse-metadata "%(album,playlist_title)s:%(meta_album)s"

# Regex extraction: "Artist - Song Title" format
--parse-metadata "title:%(artist)s - %(title)s"

# Extract year from YYYYMMDD date
--parse-metadata "upload_date:(?P<meta_year>\\d{4})"

# Clear a field (set to empty)
--parse-metadata ":(?P<synopsis>)"
```

### YouTube Music vs Regular YouTube

**Always prefer YouTube Music URLs** - they have better metadata:

| Source | Artist | Album | Track # | Year |
|--------|--------|-------|---------|------|
| `music.youtube.com` | Usually correct | Often correct | Sometimes | Usually |
| `youtube.com` | Channel name | Missing | Missing | Upload date |

```python
def normalize_youtube_url(url: str) -> str:
    """Convert regular YouTube to YouTube Music URL."""
    if "youtube.com/watch" in url and "music." not in url:
        return url.replace("youtube.com", "music.youtube.com")
    return url
```

---

## Thumbnail Handling

### The Problem

YouTube thumbnails are 16:9 (landscape), but album art should be 1:1 (square). Without processing, embedded thumbnails have ugly black bars.

### The Solution

Crop to square using FFmpeg post-processor:

```bash
--convert-thumbnails png \
--ppa "ThumbnailsConvertor+ffmpeg_o:-c:v png -vf crop=\"'if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'\""
```

This removes letterbox bars and creates a proper square thumbnail.

### Alternative: Download Separately

```bash
# Download thumbnail without embedding
--write-thumbnail \
--convert-thumbnails jpg

# Then process with ImageMagick if needed
convert thumb.jpg -gravity center -crop 1:1 cover.jpg
```

---

## Python Integration

### Search Service

```python
import subprocess
import json
from typing import List, Dict

class YouTubeService:
    def __init__(self, search_limit: int = 20):
        self.search_limit = search_limit

    def search(self, query: str) -> List[Dict]:
        """Search YouTube Music for audio content."""
        result = subprocess.run([
            "yt-dlp",
            "--flat-playlist",
            "-j",
            f"ytsearch{self.search_limit}:{query}"
        ], capture_output=True, text=True)

        results = []
        for line in result.stdout.strip().split('\n'):
            if line:
                data = json.loads(line)
                results.append({
                    "id": data["id"],
                    "title": data.get("title"),
                    "url": f"https://music.youtube.com/watch?v={data['id']}",
                    "duration": data.get("duration"),
                    "channel": data.get("channel"),
                    "artist": data.get("artist"),
                    "album": data.get("album"),
                    "thumbnail": data.get("thumbnail")
                })

        return results

    def get_metadata(self, url: str) -> Dict:
        """Get detailed metadata for a video."""
        result = subprocess.run([
            "yt-dlp",
            "-j",
            "--no-download",
            url
        ], capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"Failed to get metadata: {result.stderr}")

        data = json.loads(result.stdout)

        return {
            "id": data.get("id"),
            "title": data.get("track") or data.get("title"),
            "artist": data.get("artist") or data.get("channel") or data.get("uploader"),
            "album": data.get("album") or data.get("playlist_title") or "Unknown Album",
            "track_number": data.get("track_number") or data.get("playlist_index"),
            "year": data.get("release_year") or (data.get("upload_date") or "")[:4],
            "duration": data.get("duration"),
            "thumbnail": data.get("thumbnail"),
            "source_url": data.get("webpage_url")
        }
```

### Download Service

```python
from celery import Celery
from pathlib import Path
import subprocess
import json
import shutil

celery = Celery('barbossa')

@celery.task(queue='downloads')
def download_from_youtube(
    url: str,
    user_id: int,
    confirm_lossy: bool = False,
    metadata_override: dict = None  # User-provided corrections
):
    """Download audio from YouTube via yt-dlp."""

    # REQUIRE explicit confirmation
    if not confirm_lossy:
        raise ValueError("User must confirm lossy download")

    # Normalize to YouTube Music URL
    if "youtube.com/watch" in url and "music." not in url:
        url = url.replace("youtube.com", "music.youtube.com")

    download_path = Path("/music/downloads/youtube")
    download_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "flac", "--audio-quality", "0",
        # Thumbnail processing
        "--embed-thumbnail",
        "--convert-thumbnails", "png",
        "--ppa", 'ThumbnailsConvertor+ffmpeg_o:-c:v png -vf crop="\'if(gt(ih,iw),iw,ih)\':\'if(gt(iw,ih),ih,iw)\'"',
        # Metadata
        "--embed-metadata",
        "--parse-metadata", "playlist_index:%(track_number)s",
        "--parse-metadata", "%(album,playlist_title)s:%(meta_album)s",
        "--parse-metadata", "%(artist,channel,uploader)s:%(meta_artist)s",
        # Save info for later processing
        "--write-info-json",
        # Output
        "-o", str(download_path / "%(artist,channel)s/%(album,playlist_title)s/%(track_number,playlist_index|00)02d - %(title)s.%(ext)s"),
        "--no-overwrites",
        url
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"yt-dlp failed: {result.stderr}")

    # Find downloaded files
    downloaded_files = list(download_path.rglob("*.flac"))
    info_files = list(download_path.rglob("*.info.json"))

    if not downloaded_files:
        raise Exception("No files downloaded")

    # Extract metadata from info.json
    extracted_metadata = {}
    if info_files:
        with open(info_files[0]) as f:
            info = json.load(f)
            extracted_metadata = {
                "artist": info.get("artist") or info.get("channel") or info.get("uploader"),
                "album": info.get("album") or info.get("playlist_title") or "Unknown Album",
                "title": info.get("track") or info.get("title"),
                "track_number": info.get("track_number") or info.get("playlist_index"),
                "year": info.get("release_year") or (info.get("upload_date") or "")[:4],
                "source_url": info.get("webpage_url")
            }

    # Apply user overrides if provided
    final_metadata = {**extracted_metadata, **(metadata_override or {})}

    # If user provided overrides, re-tag the file
    if metadata_override:
        apply_metadata_tags(downloaded_files[0], final_metadata)

    # Process through import pipeline
    return process_youtube_import(
        downloaded_files[0],
        user_id,
        final_metadata
    )


def apply_metadata_tags(file_path: Path, metadata: dict):
    """Apply metadata tags to audio file using mutagen."""
    from mutagen.flac import FLAC

    audio = FLAC(str(file_path))

    if metadata.get("artist"):
        audio["artist"] = metadata["artist"]
    if metadata.get("album"):
        audio["album"] = metadata["album"]
    if metadata.get("title"):
        audio["title"] = metadata["title"]
    if metadata.get("track_number"):
        audio["tracknumber"] = str(metadata["track_number"])
    if metadata.get("year"):
        audio["date"] = metadata["year"]

    audio.save()
```

---

## User Flow: Metadata Review

**Any user can fix metadata** - not just admins. This happens before the file enters the library.

### Step 1: Show Extracted Metadata

```
+----------------------------------------------------------+
|  Downloaded from YouTube                                  |
|                                                          |
|  Extracted Metadata:                                     |
|  Artist:  [The Band_______________]  (from: channel)     |
|  Album:   [Live at Venue 2023_____]  (from: playlist)    |
|  Title:   [Song Name______________]  (from: title)       |
|  Track #: [5__]                       (from: playlist)   |
|  Year:    [2023]                      (from: upload)     |
|                                                          |
|  Thumbnail: [Preview] [Replace...]                       |
|                                                          |
|  WARNING: YouTube audio is lossy (~256kbps)             |
|                                                          |
|  [Save & Import]  [Try Beets Match]  [Cancel]           |
+----------------------------------------------------------+
```

### Step 2: User Edits (Optional)

User can:
- Edit any field directly
- Click "Try Beets Match" to attempt MusicBrainz lookup
- Replace thumbnail with custom image
- Cancel import entirely

### Step 3: Import with Corrected Metadata

```python
# User submits corrected metadata
@app.post("/api/downloads/youtube/import")
async def import_youtube_download(
    download_id: int,
    metadata: MetadataSchema,
    user: User = Depends(get_current_user)
):
    download = db.get_download(download_id)

    # Any user can fix metadata for their own downloads
    if download.user_id != user.id and not user.is_admin:
        raise HTTPException(403, "Can only edit your own downloads")

    # Apply metadata and import
    result = process_youtube_import.delay(
        download.file_path,
        user.id,
        metadata.dict()
    )

    return {"status": "importing", "task_id": result.id}
```

---

## UI Components

### Metadata Editor

```jsx
function YouTubeMetadataEditor({ extracted, onSave, onCancel }) {
  const [metadata, setMetadata] = useState(extracted);

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-white font-bold mb-4">Review Metadata</h3>

      <div className="space-y-3">
        <div>
          <label className="text-gray-400 text-sm">Artist</label>
          <input
            value={metadata.artist}
            onChange={e => setMetadata({...metadata, artist: e.target.value})}
            className="w-full bg-gray-700 text-white p-2 rounded"
          />
          <span className="text-gray-500 text-xs">Source: {extracted.artist_source}</span>
        </div>

        <div>
          <label className="text-gray-400 text-sm">Album</label>
          <input
            value={metadata.album}
            onChange={e => setMetadata({...metadata, album: e.target.value})}
            className="w-full bg-gray-700 text-white p-2 rounded"
          />
        </div>

        <div>
          <label className="text-gray-400 text-sm">Title</label>
          <input
            value={metadata.title}
            onChange={e => setMetadata({...metadata, title: e.target.value})}
            className="w-full bg-gray-700 text-white p-2 rounded"
          />
        </div>

        <div className="flex gap-4">
          <div className="flex-1">
            <label className="text-gray-400 text-sm">Track #</label>
            <input
              type="number"
              value={metadata.track_number}
              onChange={e => setMetadata({...metadata, track_number: e.target.value})}
              className="w-full bg-gray-700 text-white p-2 rounded"
            />
          </div>
          <div className="flex-1">
            <label className="text-gray-400 text-sm">Year</label>
            <input
              value={metadata.year}
              onChange={e => setMetadata({...metadata, year: e.target.value})}
              className="w-full bg-gray-700 text-white p-2 rounded"
            />
          </div>
        </div>
      </div>

      <div className="mt-4 p-3 bg-yellow-900 border border-yellow-600 rounded">
        <p className="text-yellow-200 text-sm">
          YouTube audio is lossy (~256kbps). This track will be marked accordingly.
        </p>
      </div>

      <div className="flex gap-3 mt-4">
        <button
          onClick={() => onSave(metadata)}
          className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded"
        >
          Save & Import
        </button>
        <button
          onClick={onCancel}
          className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
```

### Source Badge with Lossy Warning

```jsx
function TrackRow({ track }) {
  return (
    <div className="flex items-center gap-2">
      <span className="flex-1">{track.title}</span>

      {track.source === 'youtube' && (
        <>
          <span className="px-1.5 py-0.5 bg-red-600 text-white text-xs rounded">
            YT
          </span>
          <span className="text-yellow-500 text-xs" title="Lossy source (~256kbps)">
            lossy
          </span>
        </>
      )}

      <span className="text-gray-500 text-xs">
        {track.source_quality}
      </span>
    </div>
  );
}
```

---

## Database Entry

```sql
INSERT INTO tracks (
    title,
    artist_id,
    album_id,
    track_number,
    source,
    source_url,
    source_quality,
    is_lossy,
    sample_rate,
    bit_depth,
    imported_by_user_id
) VALUES (
    'Live at Venue',
    123,
    456,
    5,
    'youtube',
    'https://music.youtube.com/watch?v=ABC123',
    'YouTube ~256kbps',
    true,
    44100,
    16,
    1  -- User who downloaded/fixed metadata
);
```

---

## Playlist Support

```python
async def download_youtube_playlist(
    playlist_url: str,
    user_id: int,
    confirm_lossy: bool
) -> List[dict]:
    """Download all tracks from a YouTube playlist."""

    # Get playlist info
    result = subprocess.run([
        "yt-dlp",
        "--flat-playlist",
        "-j",
        playlist_url
    ], capture_output=True, text=True)

    entries = [json.loads(line) for line in result.stdout.strip().split('\n') if line]

    if len(entries) > 50:
        raise TooManyTracksError(f"Playlist has {len(entries)} tracks. Max 50.")

    # Queue downloads
    tasks = []
    for entry in entries:
        task = download_from_youtube.delay(
            f"https://music.youtube.com/watch?v={entry['id']}",
            user_id,
            confirm_lossy
        )
        tasks.append({"id": entry["id"], "title": entry.get("title"), "task_id": task.id})

    return tasks
```

---

## Error Handling

```python
YTDLP_ERRORS = {
    "Video unavailable": "This video is no longer available",
    "Private video": "This video is private",
    "Sign in to confirm your age": "Age-restricted content not supported",
    "members-only": "This video requires channel membership",
    "copyright": "Video removed due to copyright",
    "This video is not available": "Video unavailable in your region"
}

def parse_ytdlp_error(stderr: str) -> str:
    for pattern, message in YTDLP_ERRORS.items():
        if pattern.lower() in stderr.lower():
            return message
    return f"Download failed: {stderr[:200]}"
```

---

## Best Practices

1. **Always use YouTube Music URLs** - Better metadata than regular YouTube
2. **Require lossy confirmation** - Never auto-download without user acknowledgment
3. **Let users fix metadata** - Any user can edit before import
4. **Crop thumbnails to square** - Use the FFmpeg post-processor
5. **Save info.json** - For debugging and re-processing
6. **Mark as lossy** - Never pretend YouTube is lossless
7. **Log source URL** - For accountability and potential re-download
8. **Use for rare content only** - Live recordings, unreleased, remixes

---

## Troubleshooting

### "yt-dlp not found"
- Ensure yt-dlp installed: `pip install yt-dlp`
- Check PATH in Docker container

### "FFmpeg not found"
- Required for audio extraction and thumbnail processing
- Install: `apt-get install ffmpeg`

### "Video unavailable"
- Video deleted, private, or region-locked
- Try YouTube Music URL instead of regular YouTube
- Check if video still exists

### "Metadata missing or wrong"
- Use `--write-info-json` to inspect what yt-dlp found
- Use metadata editor to fix before import
- Try "Search Beets" for MusicBrainz match

### "Thumbnail has black bars"
- Ensure FFmpeg crop post-processor is configured
- Check `--ppa` syntax is correct

### "Poor audio quality"
- This is expected - YouTube is lossy
- Nothing can improve the source quality
- Consider if content is truly unavailable elsewhere
