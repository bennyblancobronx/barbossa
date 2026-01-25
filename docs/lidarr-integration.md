# Lidarr Integration

Barbossa integrates with an external Lidarr instance via API for automated music acquisition and gap filling.

## Architecture

```
+------------------+          +------------------+
|    BARBOSSA      |   API    |     LIDARR       |
|                  |<-------->|   (external)     |
|  - Family UI     |          |  - RSS feeds     |
|  - User libraries|          |  - Usenet/Torrent|
|  - Quality mgmt  |          |  - Auto-download |
+--------+---------+          +--------+---------+
         |                             |
         |                             |
         v                             v
   /music/artists              /music/downloads/lidarr
   (final destination)         (Lidarr output)
                                      |
                                      v
                              Barbossa imports
                              via watch folder
```

## Connection Setup

### Settings > Lidarr

```yaml
lidarr:
  enabled: true
  url: http://lidarr.local:8686  # Your Lidarr instance
  api_key: "your-api-key-here"   # Settings > General > API Key
  auto_request: true              # Auto-add missing to Lidarr
  fill_gaps: true                 # Use for incomplete albums
  import_path: /music/downloads/lidarr  # Watch folder (optional)
```

### Lidarr Configuration

In Lidarr, configure:

1. **Root Folder**: Point to a shared volume Barbossa can access
2. **Quality Profile**: Set to FLAC/Lossless preferred
3. **Metadata Profile**: Standard or your preference
4. **Download Clients**: Your Usenet/Torrent setup

## API Endpoints Used

### System Status
```
GET /api/v1/system/status
```
Test connection, check Lidarr is running.

### Artist Management
```
GET  /api/v1/artist                    # List all monitored artists
GET  /api/v1/artist/lookup?term=       # Search for artist
POST /api/v1/artist                    # Add artist to monitor
```

### Album Management
```
GET /api/v1/album                      # List albums
GET /api/v1/album?artistId={id}        # Albums for specific artist
```

### Commands (Trigger Actions)
```
POST /api/v1/command
{
  "name": "ArtistSearch",
  "artistId": 123
}
```

Available commands:
- `ArtistSearch` - Search for artist's music
- `AlbumSearch` - Search for specific album
- `RefreshArtist` - Refresh artist metadata
- `MissingAlbumSearch` - Search for all missing albums

### Queue & History
```
GET /api/v1/queue                      # Current download queue
GET /api/v1/history?pageSize=50        # Download history
```

## Use Cases

### 1. Request Artist via Lidarr

User searches for artist not in library, selects "Request via Lidarr":

```python
async def request_artist(artist_name: str, mbid: str):
    # 1. Search Lidarr for artist
    search = await lidarr.get(f"/api/v1/artist/lookup?term=lidarr:{mbid}")

    if not search.json():
        raise ArtistNotFound(artist_name)

    artist_data = search.json()[0]

    # 2. Add artist to Lidarr
    artist_data["monitored"] = True
    artist_data["qualityProfileId"] = get_flac_profile_id()
    artist_data["rootFolderPath"] = "/music/downloads/lidarr"

    response = await lidarr.post("/api/v1/artist", json=artist_data)
    artist_id = response.json()["id"]

    # 3. Trigger search
    await lidarr.post("/api/v1/command", json={
        "name": "ArtistSearch",
        "artistId": artist_id
    })

    return {"status": "requested", "artist_id": artist_id}
```

### 2. Fill Incomplete Albums

When Qobuz album is missing tracks:

```python
async def fill_album_gaps(album: Album):
    # Check if artist already in Lidarr
    artists = await lidarr.get("/api/v1/artist")
    existing = find_by_name(artists.json(), album.artist.name)

    if not existing:
        # Add artist first
        await request_artist(album.artist.name, album.artist.mbid)

    # Trigger album search
    lidarr_album = await find_lidarr_album(album)
    if lidarr_album:
        await lidarr.post("/api/v1/command", json={
            "name": "AlbumSearch",
            "albumIds": [lidarr_album["id"]]
        })
```

### 3. Import Completed Downloads

Watch folder approach (recommended):

```python
# In watcher service
def watch_lidarr_folder():
    observer = Observer()
    observer.schedule(
        LidarrImportHandler(),
        "/music/downloads/lidarr",
        recursive=True
    )
    observer.start()

class LidarrImportHandler(FileSystemEventHandler):
    def on_created(self, event):
        if is_complete_album(event.src_path):
            process_import.delay(
                Path(event.src_path),
                DownloadSource.LIDARR,
                user_id=SYSTEM_USER
            )
```

Alternative: Poll Lidarr history

```python
async def poll_lidarr_history():
    """Periodically check Lidarr for completed downloads."""
    last_check = get_last_check_time()

    history = await lidarr.get(
        "/api/v1/history",
        params={"eventType": "downloadFolderImported", "since": last_check}
    )

    for record in history.json()["records"]:
        album_path = record["data"]["importedPath"]
        if not already_imported(album_path):
            process_import.delay(
                Path(album_path),
                DownloadSource.LIDARR,
                user_id=SYSTEM_USER
            )

    save_last_check_time(now())
```

### 4. Show Lidarr Queue Status

Display Lidarr download progress in Barbossa UI:

```python
async def get_combined_queue():
    """Get download queue from all sources."""
    barbossa_queue = db.get_download_queue()

    lidarr_queue = await lidarr.get("/api/v1/queue")

    combined = []

    for item in barbossa_queue:
        combined.append({
            "source": item.source,
            "title": item.title,
            "status": item.status,
            "progress": item.progress
        })

    for item in lidarr_queue.json()["records"]:
        combined.append({
            "source": "lidarr",
            "title": f"{item['artist']['artistName']} - {item['album']['title']}",
            "status": item["status"],
            "progress": 100 - (item.get("sizeleft", 0) / item.get("size", 1) * 100)
        })

    return combined
```

## Quality Handling

When Lidarr downloads complete, Barbossa:

1. Extracts quality via ExifTool
2. Compares against existing tracks (if any)
3. Keeps higher quality version
4. Logs quality source: `lidarr` with quality details

```python
# Import with quality tracking
track = Track(
    source="lidarr",
    source_quality=f"{quality.sample_rate/1000}kHz/{quality.bit_depth}bit",
    is_lossy=quality.format not in ("FLAC", "ALAC", "WAV")
)
```

## Error Handling

### Connection Errors

```python
async def check_lidarr_status() -> dict:
    try:
        response = await lidarr.get("/api/v1/system/status", timeout=5)
        return {
            "connected": True,
            "version": response.json()["version"]
        }
    except httpx.ConnectError:
        return {"connected": False, "error": "Cannot reach Lidarr"}
    except httpx.TimeoutException:
        return {"connected": False, "error": "Lidarr timeout"}
```

### Artist Not Found

```python
if not search_results:
    # Fallback to MusicBrainz search
    mb_results = search_musicbrainz(artist_name)
    if mb_results:
        # Try Lidarr again with MBID
        return await request_artist(artist_name, mb_results[0]["mbid"])
    else:
        raise ArtistNotFoundError(f"Cannot find {artist_name} in Lidarr or MusicBrainz")
```

## Best Practices

1. **Use Watch Folder over Polling** - More reliable, immediate detection
2. **Set Appropriate Quality Profile** - Match Barbossa's preferences
3. **Configure Root Folder Correctly** - Shared volume both can access
4. **Handle Duplicates** - Lidarr may download what Barbossa already has
5. **Log Everything** - Track what came from Lidarr for accountability

## Troubleshooting

### "Cannot connect to Lidarr"
- Check URL and port
- Verify API key is correct
- Ensure Lidarr is running
- Check firewall/network settings

### "Artist not found"
- Try searching by MusicBrainz ID
- Check if artist name is spelled correctly
- Verify Lidarr can access indexers

### "Downloads not importing"
- Check watch folder path is correct
- Verify Barbossa has read access
- Check watcher service is running
- Look for errors in worker logs

### "Quality mismatch"
- Review Lidarr quality profile
- Check if Usenet/Torrent releases are actually FLAC
- Verify ExifTool is extracting correctly
