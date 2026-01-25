# Streamrip Integration Guide

Research compiled from [GitHub - nathom/streamrip](https://github.com/nathom/streamrip), [DeepWiki](https://deepwiki.com/nathom/streamrip), and [PyPI](https://pypi.org/project/streamrip/).

## Overview

Streamrip is a scriptable music downloader supporting Qobuz, Tidal, Deezer, and SoundCloud. Version 2.1.0 (March 2025) requires Python 3.10+.

## Installation

```bash
pip3 install streamrip --upgrade

# For latest dev features
pip3 install git+https://github.com/nathom/streamrip.git@dev

# FFmpeg required for format conversion
brew install ffmpeg  # macOS
```

## CLI Commands

### Primary Commands

| Command | Description |
|---------|-------------|
| `rip url [URL...]` | Download from direct album/track URLs |
| `rip search <service> <type> <query>` | Interactive search |
| `rip lastfm [URL]` | Download playlists from Last.fm |
| `rip config open` | Edit configuration file |
| `rip config reset` | Restore default config |
| `rip db browse` | View download history |

### Search Command

```bash
rip search <service> <type> <query>
```

**Services:** qobuz, tidal, deezer, soundcloud
**Types:** track, album, playlist, artist, label

```bash
# Examples
rip search qobuz album "fleetwood mac rumours"
rip search qobuz artist "pink floyd"
rip search qobuz track "comfortably numb"
```

Opens interactive menu for selecting results to download.

### Global Options

| Option | Description |
|--------|-------------|
| `--quality <0-4>` | Set max quality tier |
| `--codec <format>` | Convert to format (FLAC, ALAC, OPUS, MP3, VORBIS, AAC) |
| `--folder <path>` | Override download directory |
| `--no-db` | Skip database, allow duplicate downloads |
| `--verbose` | Enable debug output |

## Quality Tiers

| Tier | Format | Availability |
|------|--------|--------------|
| 0 | 128 kbps MP3/AAC | Deezer, Tidal, SoundCloud |
| 1 | 320 kbps MP3/AAC | Deezer, Tidal, Qobuz, SoundCloud |
| 2 | 16-bit/44.1kHz FLAC (CD) | Deezer, Tidal, Qobuz |
| 3 | 24-bit/96kHz | Tidal (MQA), Qobuz |
| 4 | 24-bit/192kHz | **Qobuz only** |

**For Barbossa:** Default to quality 4 (max) since we're using Qobuz.

## Configuration

Location: `~/.config/streamrip/config.toml`

### Key Settings for Barbossa

```toml
[downloads]
folder = "/music/downloads"
source_subdirectories = false

[qobuz]
quality = 4
email = ""
password = ""

[filepaths]
# Customize naming - default works well for Plex

[metadata]
# Cover art settings

[database]
# SQLite database for tracking downloads
```

### Database (Duplicate Prevention)

Streamrip maintains SQLite database with:
- `Downloads` table - successful downloads
- `Failed` table - failed attempts with source/type/ID

**Important:** This handles streamrip-level deduplication. Barbossa needs additional deduplication for:
- Different quality versions
- Deluxe editions
- Cross-source duplicates

## Python API

Streamrip is primarily CLI-focused but can be scripted:

```python
# Core classes
from streamrip import Main, Config
from streamrip.clients import QobuzClient
from streamrip.media import Track, Album, Playlist

# Clients communicate with service APIs
# Media classes parse metadata into downloadable form
```

Uses async/await patterns via `aiohttp` for concurrent downloads.

## Barbossa Integration Strategy

### Search Flow

```
User searches in Barbossa
    |
    v
Barbossa calls: rip search qobuz <type> "<query>"
    |
    v
Parse interactive output OR use Python API directly
    |
    v
Display results in Barbossa UI
    |
    v
User selects item -> Barbossa triggers download
```

### Download Flow

```
User requests track/album
    |
    v
Always download full album (even for single track request)
    |
    v
rip --quality 4 url "<qobuz_url>"
    |
    v
Downloaded to /music/downloads
    |
    v
Beets import pipeline processes files
    |
    v
Move to master library with Plex naming
    |
    v
If single track requested -> auto-add to user library
If full album -> do NOT auto-add (user must heart)
```

### Best Practices from Research

1. **Search type selection:** Force user to select artist/album/track type before search
   - Prevents ambiguous results
   - Maps cleanly to streamrip's search types

2. **No playlist search in main UI**
   - Playlists handled via Last.fm integration
   - Spotify/Apple Music playlists work through Last.fm URLs

3. **Quality:** Always use tier 4 for Qobuz (24-bit/192kHz when available)

4. **Database:** Let streamrip handle its own dupe database
   - Barbossa adds second layer for quality comparison
   - ExifTool extracts actual sample rate for verification

## CLI Examples for Barbossa Backend

```bash
# Interactive search (opens menu)
rip search qobuz album "dark side of the moon"

# Scripted search (outputs to file for parsing)
rip search qobuz album "dark side of the moon" -n 20 -o /tmp/results.txt

# Download by URL
rip --quality 4 url "https://www.qobuz.com/us-en/album/..."

# Download with specific folder
rip --quality 4 --folder /music/downloads url "https://..."

# Force re-download (skip database)
rip --no-db url "https://..."
```

## Soundcloud Support

Streamrip supports Soundcloud as a source. However, quality is limited compared to Qobuz.

### Soundcloud Quality Tiers

| Tier | Format | Notes |
|------|--------|-------|
| 0 | 128 kbps MP3 | Free tier |
| 1 | 256 kbps AAC | Go+ subscription |

### Soundcloud CLI

```bash
# Search Soundcloud
rip search soundcloud track "artist name song"
rip search soundcloud album "artist name"
rip search soundcloud playlist "playlist name"

# Download by URL
rip url "https://soundcloud.com/artist/track-name"
rip url "https://soundcloud.com/artist/sets/album-name"
```

### Soundcloud Limitations

- **No lossless** - Max 256kbps AAC (Go+) or 128kbps MP3 (free)
- **Go+ tracks** - Premium tracks may only provide 30-second previews without subscription
- **Metadata** - Often incomplete or user-provided (less reliable than Qobuz)
- **Availability** - Some tracks region-locked or removed

### Barbossa Integration

For Soundcloud in Barbossa:
1. User pastes Soundcloud URL in Downloads page URL field
2. Streamrip (or yt-dlp as fallback) handles download
3. Track marked as `source: soundcloud`, `is_lossy: true`
4. Quality warning shown before download

### When to Use Soundcloud

- DJ mixes not on Qobuz
- Remixes and bootlegs
- Unreleased/exclusive tracks
- Podcasts and spoken word

**Priority:** Always check Qobuz first. Soundcloud is a fallback for content not available elsewhere.

### Configuration

```toml
# In streamrip config.toml
[soundcloud]
quality = 1  # 0=128kbps, 1=256kbps (Go+ required)
client_id = ""  # Optional, auto-generated if empty
app_version = ""  # Optional
```

## Requirements

- Python 3.10+
- FFmpeg (for conversion)
- Qobuz premium subscription
- Soundcloud Go+ (optional, for 256kbps)
- pip/pipx for installation
