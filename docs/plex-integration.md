# Plex Integration

Barbossa integrates with Plex Media Server to automatically trigger library scans when music is imported.

## Requirements

- Plex Media Server with music library configured
- Plex authentication token
- Network access from Barbossa to Plex server

## Getting Plex Token

### Method 1: From Plex Web
1. Open Plex Web App, sign in
2. Play any media
3. Open browser DevTools (F12) > Network tab
4. Look for requests to your server
5. Find `X-Plex-Token` parameter in URL

### Method 2: From XML
```
http://YOUR_PLEX_IP:32400/library/sections?X-Plex-Token=YOUR_TOKEN
```
If you can access this, your token is valid.

### Method 3: Via PlexAPI Python
```python
from plexapi.myplex import MyPlexAccount

account = MyPlexAccount('username', 'password')
plex = account.resource('Server Name').connect()
print(plex._token)
```

## Configuration

```yaml
# config.yml
plex:
  enabled: true
  url: http://192.168.1.100:32400  # Your Plex server
  token: "your-plex-token-here"
  music_library_id: 3               # Section ID for music library
  auto_scan: true                   # Trigger scan on import
```

## API Endpoints

### Get Library Sections (find your music library ID)
```bash
curl "http://PLEX_IP:32400/library/sections?X-Plex-Token=TOKEN"
```

Response includes section IDs:
```xml
<Directory key="3" type="artist" title="Music" ... />
```

### Scan Entire Music Library
```bash
curl "http://PLEX_IP:32400/library/sections/3/refresh?X-Plex-Token=TOKEN"
```
- Returns immediately (scan runs in background)
- No response body

### Scan Specific Path (Recommended)
```bash
curl "http://PLEX_IP:32400/library/sections/3/refresh?path=%2Fmusic%2Flibrary%2FArtist%20Name&X-Plex-Token=TOKEN"
```
- Path must be URL-encoded
- Faster than full library scan
- Use when importing single album/artist

### Refresh Metadata Only
```bash
curl "http://PLEX_IP:32400/library/sections/3/refresh?force=1&X-Plex-Token=TOKEN"
```
- Re-downloads metadata even if present
- Use when metadata was wrong

## Python Integration

### Using requests
```python
import requests
from urllib.parse import quote

PLEX_URL = "http://192.168.1.100:32400"
PLEX_TOKEN = "your-token"
MUSIC_SECTION_ID = 3

def scan_library():
    """Scan entire music library."""
    url = f"{PLEX_URL}/library/sections/{MUSIC_SECTION_ID}/refresh"
    response = requests.get(url, params={"X-Plex-Token": PLEX_TOKEN})
    return response.status_code == 200

def scan_path(path: str):
    """Scan specific artist/album folder."""
    url = f"{PLEX_URL}/library/sections/{MUSIC_SECTION_ID}/refresh"
    response = requests.get(url, params={
        "X-Plex-Token": PLEX_TOKEN,
        "path": path  # requests handles URL encoding
    })
    return response.status_code == 200

# After importing Pink Floyd album:
scan_path("/music/artists/Pink Floyd/The Dark Side of the Moon (1973)")
```

### Using PlexAPI library
```python
from plexapi.server import PlexServer

PLEX_URL = "http://192.168.1.100:32400"
PLEX_TOKEN = "your-token"

plex = PlexServer(PLEX_URL, PLEX_TOKEN)
music = plex.library.section('Music')

# Scan entire library
music.update()

# Scan specific location (requires path in library)
music.update(path="/music/artists/Pink Floyd")

# Refresh metadata for specific album
album = music.searchAlbums(title="The Dark Side of the Moon")[0]
album.refresh()
```

## Barbossa Integration

### After Import
```python
async def on_import_complete(album_path: str):
    """Called after beets finishes importing."""
    # 1. Index in Barbossa database
    await index_album(album_path)

    # 2. Trigger Plex scan for just this album
    if settings.plex.enabled and settings.plex.auto_scan:
        await scan_plex_path(album_path)
        log.info(f"Plex scan triggered for {album_path}")
```

### Batch Import
```python
async def on_batch_import_complete(artist_paths: list[str]):
    """Called after importing multiple albums."""
    # Get unique artists
    artists = set(Path(p).parent for p in artist_paths)

    for artist_path in artists:
        await scan_plex_path(str(artist_path))

    # Or scan whole library if many changes
    if len(artists) > 10:
        await scan_plex_library()
```

## Error Handling

```python
async def scan_plex_path(path: str) -> dict:
    try:
        response = await httpx.get(
            f"{PLEX_URL}/library/sections/{MUSIC_SECTION_ID}/refresh",
            params={"X-Plex-Token": PLEX_TOKEN, "path": path},
            timeout=10
        )
        if response.status_code == 200:
            return {"success": True}
        elif response.status_code == 401:
            return {"success": False, "error": "Invalid Plex token"}
        elif response.status_code == 404:
            return {"success": False, "error": "Library section not found"}
        else:
            return {"success": False, "error": f"Plex returned {response.status_code}"}
    except httpx.ConnectError:
        return {"success": False, "error": "Cannot reach Plex server"}
    except httpx.TimeoutException:
        return {"success": False, "error": "Plex request timeout"}
```

## Settings UI

```
Settings > Plex Integration

Plex Server URL:  [http://192.168.1.100:32400____]
Plex Token:       [••••••••••••••••••••••_______] [Test Connection]
Music Library:    [Music (Section 3)___________▼]

[x] Auto-scan on import
[ ] Refresh metadata after scan

Status: Connected (Plex Media Server 1.40.0)
```

## CLI Commands

### Test connection
```bash
curl -s "http://PLEX_IP:32400/?X-Plex-Token=TOKEN" | grep -o 'version="[^"]*"'
```

### List all libraries
```bash
curl -s "http://PLEX_IP:32400/library/sections?X-Plex-Token=TOKEN" | \
  grep -oP 'key="\K[^"]*|title="\K[^"]*' | paste - -
```

### Check library scan status
```bash
curl -s "http://PLEX_IP:32400/library/sections/3?X-Plex-Token=TOKEN" | \
  grep -oP 'refreshing="\K[^"]*'
```

## Troubleshooting

### "Cannot reach Plex server"
- Check URL and port (default 32400)
- Ensure Plex is running
- Check firewall/network between Barbossa and Plex

### "Invalid Plex token"
- Token may have expired
- Re-authenticate and get new token
- Check token has access to server

### "Library section not found"
- Run library sections endpoint to get correct ID
- Music library may have different ID after recreation

### "Scan not updating"
- Plex may not see files if path mapping differs
- Check Plex library path vs Barbossa library path
- Both must see `/music/artists/` at same location

### Path Mapping (Docker)
If Barbossa and Plex have different mounts:
```python
def translate_path(barbossa_path: str) -> str:
    """Convert Barbossa path to Plex path."""
    # Barbossa: /music/artists/Artist/Album
    # Plex:     /data/music/Artist/Album
    return barbossa_path.replace("/music/artists", "/data/music")
```
