# TorrentLeech Integration Guide

Research compiled from your local TorrentLeech documentation and [torrent-search-api](https://github.com/JimmyLaurent/torrent-search-api).

## Overview

TorrentLeech provides an API for uploaders to upload, download, and search torrents. This is an **admin-only** feature in Barbossa for sharing high-quality music rips.

## API Endpoints

| Endpoint | URL | Method |
|----------|-----|--------|
| Upload | `https://www.torrentleech.org/torrents/upload/apiupload` | POST |
| Download | `https://www.torrentleech.org/torrents/upload/apidownload` | POST |
| Search | `https://www.torrentleech.org/api/torrentsearch` | POST |

## Authentication

Uses **Torrent Passkey** (32 characters) found in TorrentLeech Profile settings.

- Same key for API calls (`announcekey` parameter)
- Same key in torrent announce URLs
- **No separate API key exists**

## Search API (Pre-existence Check)

**This answers the question: Can we check if release already exists?**

Yes, the Search API allows checking before upload.

```bash
curl "https://www.torrentleech.org/api/torrentsearch" \
  -d "announcekey=YOUR_32_CHAR_KEY" \
  -d "exact=1" \
  -d "query='Artist.Album.2024.FLAC-Group'"
```

### Parameters

| Field | Required | Description |
|-------|----------|-------------|
| `announcekey` | Yes | Your 32-char passkey |
| `query` | Yes | Search term in **single quotes** |
| `exact` | No | Set to `1` for exact match |

### Response

| Response | Meaning |
|----------|---------|
| `0` | Not found - safe to upload |
| `1` | Found - duplicate exists |

### Known Issues (Feb 2025)

- `exact=1` may still match partial names
- Example: `Harlem.S03E05` matches `Godfather.of.Harlem.S03E05`
- **Workaround:** Manual site search to verify before upload

## Upload API

### Music Category

| Category | Cat # | Description |
|----------|-------|-------------|
| Audio | 31 | MP3, FLAC, OGG - all audio |
| Music Videos | 16 | Anything with video |

### Required Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `announcekey` | Yes | string | 32-char passkey |
| `category` | Yes | integer | 31 for audio |
| `nfo` OR `description` | Yes | file/string | NFO file or text |
| `torrent` | Yes | file | .torrent file |
| `tags` | No | string | Comma-separated tags |

### Upload Example

```bash
curl -X POST \
  -F 'announcekey=YOUR_32_CHAR_KEY' \
  -F 'category=31' \
  -F 'nfo=@release.nfo' \
  -F 'tags=FLAC,Lossless,24bit' \
  -F 'torrent=@Artist.Album.2024.FLAC-Group.torrent' \
  https://www.torrentleech.org/torrents/upload/apiupload
```

### Response

- **Success:** Returns numeric torrent ID
- **Failure:** Returns error text

## Creating Torrent Files

### Required Settings

| Setting | Value |
|---------|-------|
| Tracker URL | `https://tracker.torrentleech.org` |
| Source tag | `TorrentLeech.org` (case sensitive) |
| Private flag | Yes |
| Piece size | Target 1500-2200 pieces |

### Piece Size Table

| Total Size | Piece Size | mktorrent `-l` |
|------------|------------|----------------|
| < 50 MB | 32 KB | 15 |
| 50-150 MB | 64 KB | 16 |
| 150-350 MB | 128 KB | 17 |
| 350-512 MB | 256 KB | 18 |
| 512 MB - 1 GB | 512 KB | 19 |
| 1-2 GB | 1 MB | 20 |
| 2-4 GB | 2 MB | 21 |
| 4-8 GB | 4 MB | 22 |

### mktorrent Command

```bash
mktorrent \
  -a "https://tracker.torrentleech.org" \
  -s "TorrentLeech.org" \
  -l 20 \
  -p \
  -o "Artist.Album.2024.FLAC-Group.torrent" \
  "/path/to/album/folder"
```

| Flag | Purpose |
|------|---------|
| `-a` | Tracker announce URL |
| `-s` | Source tag (enables immediate seeding) |
| `-l` | Piece size as power of 2 |
| `-p` | Private torrent |
| `-o` | Output filename |

## Music Naming Convention

```
Artist.Name.Album.Name.Source.Audio.Codec-ReleaseGroup
```

**Examples:**
- `Tool.Lateralus.CD.MP3-MARiBOR`
- `Pink.Floyd.The.Dark.Side.of.the.Moon.1973.CD.FLAC-Group`
- `Taylor.Swift.Midnights.2022.WEB.FLAC-Group`

**Rules:**
- Use dots (`.`) as separators, never spaces
- Include year when possible
- Include source (CD, WEB, Vinyl)
- Include codec (FLAC, MP3)

## NFO Requirements

Every torrent requires an NFO containing MediaInfo output:

```bash
# Generate NFO from audio file
mediainfo "/path/to/track.flac" > release.nfo

# Anonymize - remove file paths
mediainfo "/path/to/track.flac" | grep -v "Complete name" > release.nfo
```

## Barbossa Integration Flow

### Admin Upload Feature

```
Admin hovers album (1 second delay)
    |
    v
Upload button appears (top-right)
    |
    v
Admin clicks upload
    |
    v
Barbossa checks: Does this exist on TorrentLeech?
    |
    +--[Search API returns 1]-> Show "Already exists" warning
    |
    +--[Search API returns 0]-> Proceed with upload
            |
            v
        Generate NFO from album files
            |
            v
        Create .torrent with mktorrent
            |
            v
        Upload via API
            |
            v
        Start seeding (return torrent file, add to client)
            |
            v
        Show success with torrent ID
```

### Pre-Check Search

```python
def check_torrentleech_exists(artist: str, album: str, year: str, codec: str) -> bool:
    """Check if release exists on TorrentLeech."""
    release_name = f"{artist}.{album}.{year}.{codec}".replace(" ", ".")

    response = requests.post(
        "https://www.torrentleech.org/api/torrentsearch",
        data={
            "announcekey": config.torrentleech_key,
            "exact": "1",
            "query": f"'{release_name}'"
        }
    )

    # Returns "0" or "1" as text
    return response.text.strip() == "1"
```

### Upload Function

```python
def upload_to_torrentleech(album_path: Path, nfo_path: Path, torrent_path: Path) -> int:
    """Upload album to TorrentLeech. Returns torrent ID."""

    with open(nfo_path, 'rb') as nfo, open(torrent_path, 'rb') as torrent:
        response = requests.post(
            "https://www.torrentleech.org/torrents/upload/apiupload",
            files={
                'nfo': nfo,
                'torrent': torrent
            },
            data={
                'announcekey': config.torrentleech_key,
                'category': '31',  # Audio
                'tags': 'FLAC,Lossless'
            }
        )

    # Success returns numeric ID, failure returns error text
    try:
        return int(response.text)
    except ValueError:
        raise UploadError(response.text)
```

## Alternative: torrent-search-api (Node.js)

For broader torrent search (not just TorrentLeech):

```javascript
const TorrentSearchApi = require('torrent-search-api');

// Enable TorrentLeech (requires credentials)
TorrentSearchApi.enableProvider('TorrentLeech', 'username', 'password');

// Search
const results = await TorrentSearchApi.search('Pink Floyd', 'Music', 20);

// Get magnet
const magnet = await TorrentSearchApi.getMagnet(results[0]);
```

**Providers:** TorrentLeech, 1337x, ThePirateBay, Rarbg, YTS, and more.

## Seeding Requirements

| Requirement | Details |
|-------------|---------|
| Minimum | Until **10 copies exist** OR **1 week** |
| Delete window | 24 hours to self-delete |

## Configuration for Barbossa

```yaml
torrent_leech:
  enabled: true
  announce_key: "your-32-character-passkey"
  auto_seed: true
  torrent_client: "qbittorrent"  # or transmission
  client_host: "localhost:8080"

  # Upload settings
  default_tags: ["FLAC", "Lossless"]
  generate_nfo: true

  # Search settings
  pre_check_exists: true
  exact_match: true
```

## Summary

**Q: Does TorrentLeech have search API for pre-existence check?**
A: Yes - `/api/torrentsearch` returns 0 (not found) or 1 (found)

**Q: Can we upload programmatically?**
A: Yes - `/torrents/upload/apiupload` with announcekey, category, nfo, torrent file

**Q: What's needed for music uploads?**
A: Category 31, proper naming convention, NFO with MediaInfo, private torrent with source tag
