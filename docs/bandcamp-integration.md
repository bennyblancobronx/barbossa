# Bandcamp Integration

Barbossa supports two methods for Bandcamp content:

1. **Free/Preview tracks** - via yt-dlp (URL paste)
2. **Purchased albums** - via bandcamp-collection-downloader

## Download Methods

| Method | Content | Quality | How |
|--------|---------|---------|-----|
| URL paste (yt-dlp) | Free tracks, name-your-price | 128kbps MP3 | Downloads page URL field |
| Collection downloader | Purchased albums | FLAC/MP3/etc | Settings > Bandcamp Sync |

## Method 1: Free Tracks via yt-dlp

Paste any Bandcamp URL into the Downloads page URL field:
```
https://artist.bandcamp.com/track/song-name
https://artist.bandcamp.com/album/album-name
```

yt-dlp handles extraction automatically. Quality is limited to 128kbps MP3 (streaming quality).

### Supported URLs
- Individual tracks: `https://artist.bandcamp.com/track/...`
- Full albums: `https://artist.bandcamp.com/album/...`
- Artist discography: `https://artist.bandcamp.com/music`

### Limitations
- Only 128kbps MP3 (stream quality)
- No FLAC for free tracks
- Metadata may be incomplete

## Method 2: Purchased Albums

For albums you've purchased on Bandcamp, use the collection sync feature.

### Tool: bandcamp-collection-downloader

Repository: https://github.com/Ezwen/bandcamp-collection-downloader

Official: https://framagit.org/Ezwen/bandcamp-collection-downloader

### Installation (Docker)
```dockerfile
# Add to Barbossa Dockerfile
RUN apt-get update && apt-get install -y openjdk-17-jre-headless
RUN curl -L https://framagit.org/Ezwen/bandcamp-collection-downloader/-/releases/permalink/latest/downloads/bandcamp-collection-downloader.jar \
    -o /opt/bandcamp-collection-downloader.jar
```

### Authentication

Bandcamp requires browser cookies for authentication (no public API).

#### Getting Cookies
1. Log into Bandcamp in Firefox or Chrome
2. Export cookies using browser extension or DevTools
3. Save as `cookies.txt` in Netscape format

#### Cookie Format (cookies.txt)
```
# Netscape HTTP Cookie File
.bandcamp.com	TRUE	/	TRUE	0	identity	YOUR_IDENTITY_VALUE
.bandcamp.com	TRUE	/	TRUE	0	session	YOUR_SESSION_VALUE
```

### CLI Usage

```bash
# Download entire collection to FLAC
java -jar bandcamp-collection-downloader.jar \
  --cookies-file /config/bandcamp-cookies.txt \
  --audio-format flac \
  /music/downloads/bandcamp

# Download specific format
java -jar bandcamp-collection-downloader.jar \
  --cookies-file /config/bandcamp-cookies.txt \
  --audio-format mp3-320 \
  /music/downloads/bandcamp

# Skip already downloaded
java -jar bandcamp-collection-downloader.jar \
  --cookies-file /config/bandcamp-cookies.txt \
  --audio-format flac \
  --skip-existing \
  /music/downloads/bandcamp
```

### Available Formats
- `flac` - Lossless (recommended)
- `wav` - Uncompressed
- `aac-hi` - AAC 256kbps
- `mp3-320` - MP3 320kbps
- `mp3-v0` - MP3 V0 VBR
- `vorbis` - Ogg Vorbis
- `alac` - Apple Lossless
- `aiff-lossless` - AIFF

### Python Wrapper

```python
import subprocess
from pathlib import Path

async def sync_bandcamp_collection(
    cookies_file: str,
    output_dir: str = "/music/downloads/bandcamp",
    audio_format: str = "flac"
) -> dict:
    """Sync user's Bandcamp purchases."""

    cmd = [
        "java", "-jar", "/opt/bandcamp-collection-downloader.jar",
        "--cookies-file", cookies_file,
        "--audio-format", audio_format,
        "--skip-existing",
        output_dir
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        # Parse output to find new albums
        new_albums = parse_download_output(result.stdout)
        return {"success": True, "new_albums": new_albums}
    else:
        return {"success": False, "error": result.stderr}

def parse_download_output(output: str) -> list:
    """Extract downloaded album paths from output."""
    albums = []
    for line in output.split("\n"):
        if "Downloaded:" in line or "Downloading:" in line:
            # Extract path from output
            path = line.split(":")[-1].strip()
            if path:
                albums.append(path)
    return albums
```

### Integration Flow

```
1. User configures Bandcamp in Settings
   - Uploads cookies.txt file
   - Sets preferred format (FLAC)

2. Manual or scheduled sync
   Settings > Bandcamp > [Sync Collection]

3. Downloads to /music/downloads/bandcamp/

4. Barbossa import pipeline processes:
   - Beets: metadata, artwork, naming
   - ExifTool: quality extraction
   - Dupe check against existing library
   - Move to /music/artists/

5. Plex scan triggered
```

## Configuration

```yaml
# config.yml
bandcamp:
  enabled: true
  cookies_file: /config/bandcamp-cookies.txt
  audio_format: flac
  download_path: /music/downloads/bandcamp
  auto_sync: false          # Manual sync only by default
  sync_schedule: "0 3 * * *"  # Optional: daily at 3am
```

## Settings UI

```
Settings > Bandcamp

Authentication:
  Cookie File: [bandcamp-cookies.txt_____] [Upload New]
  Status: Authenticated as "username"

Download Format:
  [FLAC (Lossless)_______________▼]

Sync Options:
  [ ] Auto-sync collection daily
  Last sync: 2026-01-20 03:00:00 (5 new albums)

[Sync Now]  [View Collection]
```

## Handling Bandcamp Downloads

After sync, albums land in `/music/downloads/bandcamp/` with structure:
```
/music/downloads/bandcamp/
└── Artist Name - Album Title/
    ├── cover.jpg
    ├── 01 - Track One.flac
    ├── 02 - Track Two.flac
    └── ...
```

Barbossa's import pipeline handles:
1. Move to watch folder or process directly
2. Beets normalizes metadata and renames
3. Quality tracked as source: `bandcamp`
4. Move to master library

## Error Handling

### "Cookies expired"
```python
async def check_bandcamp_auth(cookies_file: str) -> dict:
    """Verify Bandcamp cookies are still valid."""
    # Try to access collection API
    # Returns error if cookies expired
    pass
```

UI shows: "Bandcamp session expired. Please upload new cookies."

### "Download failed"
- Check disk space
- Verify cookies still valid
- Some albums may be region-locked

### "Album not in collection"
- Can only download purchased albums
- Free downloads must be "purchased" (even at $0)

## Alternative Tools

### iliana/bandcamp-dl (Python)
```bash
pip install bandcamp-dl
bandcamp-dl --cookies cookies.txt --output /music/downloads/bandcamp
```
Simpler but fewer options.

### scdl (for Soundcloud comparison)
Note: Bandcamp and Soundcloud are different platforms. This doc covers Bandcamp only.

## Quality Notes

| Source | Max Quality | Lossy? |
|--------|-------------|--------|
| Purchased (FLAC) | 24/96 or 16/44.1 | No |
| Purchased (MP3-320) | 320kbps | Yes |
| Free/URL paste | 128kbps | Yes |

Always prefer purchased FLAC when available. URL paste is for preview/discovery only.

## Troubleshooting

### "Cannot authenticate"
- Re-export cookies from browser
- Make sure you're logged into bandcamp.com
- Cookie format must be Netscape HTTP Cookie File

### "No albums found"
- Check Bandcamp collection at bandcamp.com/username/collection
- Ensure purchases are in your collection
- Some label/artist pages have separate collections

### "Download incomplete"
- Check disk space
- Network timeout - retry
- Some very old purchases may have issues

### "Wrong metadata"
- Bandcamp metadata is artist-provided
- May need manual fixes in Barbossa
- Beets can help correct via MusicBrainz lookup
