# Beets Integration Guide

Research compiled from [beets.io](https://beets.io/), [beets documentation](https://beets.readthedocs.io/), and [GitHub](https://github.com/beetbox/beets).

## Overview

Beets is a music library manager and MusicBrainz tagger. Current version: 2.5.1. For Barbossa, beets handles:
- Metadata correction via MusicBrainz
- File organization with Plex-compatible naming
- Album art fetching
- Lyrics downloading
- Duplicate detection

## Installation

```bash
pip install beets

# With optional dependencies
pip install beets[fetchart,lyrics,lastgenre,chroma]

# Or via pipx for isolation
pipx install beets
```

## Configuration

Location: `~/.config/beets/config.yaml`

### Complete Barbossa Configuration

```yaml
# Paths
directory: /music/library
library: /config/beets/library.db

# Import settings
import:
    move: yes              # Move files (not copy) to save space
    write: yes             # Write tags to files
    autotag: yes           # Enable MusicBrainz lookup
    timid: no              # Don't require confirmation on good matches
    quiet: no              # Show import prompts
    log: /config/beets/import.log

# Path formats - Plex compatible
paths:
    default: $albumartist/$album%aunique{} ($year)/$track - $title
    singleton: Non-Album/$artist/$title
    comp: Compilations/$album%aunique{} ($year)/$track - $title
    albumtype:soundtrack: Soundtracks/$album%aunique{} ($year)/$track - $title

# Character replacement for filesystem safety
replace:
    '[\\/]': _
    '^\.': _
    '[\x00-\x1f]': _
    '[<>:"\?\*\|]': _
    '\.$': _
    '\s+$': ''
    '^\s+': ''
    '^-': _

# ASCII-safe paths
asciify_paths: yes

# Album art filename
art_filename: cover

# Plugins
plugins:
    - musicbrainz
    - fetchart
    - embedart
    - lyrics
    - lastgenre
    - scrub
    - duplicates
    - missing
    - info
    - edit

# MusicBrainz settings
musicbrainz:
    ratelimit: 1           # 1 request/second (required for public server)
    extra_tags: [year, label, catalognum, country, media]

# Fetch album art
fetchart:
    auto: yes
    minwidth: 500
    maxwidth: 1200
    quality: 90
    sources:
        - filesystem
        - coverart
        - itunes
        - amazon
        - albumart
    store_source: yes

# Embed art in files
embedart:
    auto: yes
    maxwidth: 500
    remove_art_file: no    # Keep cover.jpg alongside files

# Lyrics
lyrics:
    auto: yes
    fallback: ''
    sources:
        - genius
        - lyricwiki
        - musixmatch

# Genre from Last.fm
lastgenre:
    auto: yes
    count: 3               # Max 3 genres
    fallback: ''
    prefer_specific: yes
    source: album

# Clean junk metadata
scrub:
    auto: yes

# Match thresholds
match:
    strong_rec_thresh: 0.04    # Auto-accept threshold
    medium_rec_thresh: 0.25    # Suggest but ask
    max_rec:
        missing_tracks: medium
        unmatched_tracks: medium
```

## Path Format Fields

### Common Fields

| Field | Description | Example |
|-------|-------------|---------|
| `$albumartist` | Album artist (use this, not $artist) | "Pink Floyd" |
| `$album` | Album title | "The Dark Side of the Moon" |
| `$year` | Release year | "1973" |
| `$track` | Track number (zero-padded) | "01" |
| `$title` | Track title | "Speak to Me" |
| `$disc` | Disc number | "1" |
| `$genre` | Genre | "Progressive Rock" |
| `$format` | Audio format | "FLAC" |
| `$bitdepth` | Bit depth | "24" |
| `$samplerate` | Sample rate | "96000" |

### Functions

| Function | Purpose | Example |
|----------|---------|---------|
| `%aunique{}` | Disambiguate duplicate albums | `[2008]` vs `[2010]` |
| `%upper{text}` | Uppercase | `%upper{$genre}` |
| `%left{text,n}` | First n chars | `%left{$albumartist,1}` = "P" |
| `%if{cond,true,false}` | Conditional | `%if{$comp,Compilations,$albumartist}` |
| `%asciify{text}` | ASCII-safe | Removes accents |

### Plex-Compatible Path Format

```yaml
paths:
    default: $albumartist/$album ($year)/$track - $title
```

Produces:
```
/music/library/
└── Pink Floyd/
    └── The Dark Side of the Moon (1973)/
        ├── cover.jpg
        ├── 01 - Speak to Me.flac
        ├── 02 - Breathe.flac
        └── ...
```

**Important:** Always use `$albumartist` not `$artist` to keep compilation albums together.

## CLI Commands

### Import

```bash
# Standard import with autotagger
beet import /music/downloads/album

# Import without moving files
beet import -C /path/to/music

# Quick import (no autotag)
beet import -A /path/to/music

# Singleton mode (individual tracks)
beet import -s /path/to/tracks

# Quiet mode (skip uncertain)
beet import -q /path/to/music

# Resume interrupted import
beet import -p /path/to/music
```

### Query Library

```bash
# Search tracks
beet ls pink floyd

# Search albums
beet ls -a dark side

# Show paths
beet ls -p pink floyd

# Custom format
beet ls -f '$artist - $title [$format $bitdepth/$samplerate]' query

# Album info
beet info -a "dark side of the moon"

# Track info with all fields
beet info --summarize /path/to/file.flac
```

### Maintenance

```bash
# Find duplicates
beet duplicates

# Find missing tracks
beet missing

# Update metadata
beet update

# Fetch missing art
beet fetchart

# Fetch missing lyrics
beet lyrics

# Edit metadata interactively
beet edit query

# Show stats
beet stats
```

## Import Options (Interactive)

When beets needs input during import:

| Key | Action |
|-----|--------|
| **A** | Apply suggested match |
| **M** | Show more candidates |
| **S** | Skip this album |
| **U** | Use as-is (no tag changes) |
| **T** | Import as individual tracks |
| **G** | Group tracks by metadata |
| **E** | Enter manual search |
| **I** | Enter MusicBrainz ID directly |
| **B** | Cancel (abort import) |

## Barbossa Integration

### Import Pipeline

```
Streamrip downloads to /music/downloads/
    |
    v
Barbossa triggers: beet import /music/downloads/album
    |
    v
Beets autotags via MusicBrainz
    |
    v
Beets moves to /music/library/ with Plex naming
    |
    v
Beets fetches cover.jpg and lyrics
    |
    v
ExifTool extracts quality data for Barbossa DB
    |
    v
Barbossa indexes new album
```

### Automation Script

```python
import subprocess
from pathlib import Path

def import_album(download_path: Path) -> bool:
    """Import downloaded album via beets."""
    result = subprocess.run(
        ["beet", "import", "-q", str(download_path)],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        return True
    else:
        # Log error, may need manual intervention
        log_import_error(download_path, result.stderr)
        return False
```

### Quality Data Extraction

After beets import, extract quality info:

```python
def get_track_quality(file_path: Path) -> dict:
    """Extract audio quality using beets info command."""
    result = subprocess.run(
        ["beet", "info", "-l", str(file_path)],
        capture_output=True,
        text=True
    )

    # Parse output for bitdepth, samplerate, format
    # Or use ExifTool for more detailed extraction
```

### Duplicate Detection Integration

Beets has built-in duplicate detection:

```bash
# List duplicates
beet duplicates

# With format
beet duplicates -f '$albumartist - $album - $title'
```

Barbossa adds quality-aware comparison on top:
1. Beets finds duplicates by metadata
2. Barbossa compares sample rate, bit depth
3. Keep higher quality version

## Plugins for Barbossa

### Essential

| Plugin | Purpose |
|--------|---------|
| `musicbrainz` | Core autotagger |
| `fetchart` | Download album covers |
| `embedart` | Embed art in files |
| `lyrics` | Download lyrics |
| `scrub` | Clean junk metadata |

### Recommended

| Plugin | Purpose |
|--------|---------|
| `lastgenre` | Genre from Last.fm |
| `duplicates` | Find duplicates |
| `missing` | Find missing tracks |
| `edit` | Manual metadata editing |
| `info` | Display track info |

### Optional

| Plugin | Purpose |
|--------|---------|
| `chroma` | Acoustic fingerprinting (slower but better for untagged) |
| `fromfilename` | Guess tags from filename |
| `replaygain` | Volume normalization |
| `convert` | Transcode to other formats |
| `plexupdate` | Notify Plex of changes |

## Handling Import Failures

For albums that fail autotag:

1. **Manual search**: Use `E` option with correct artist/album
2. **MusicBrainz ID**: Use `I` option with MB release ID
3. **As-is import**: Use `U` to keep existing tags
4. **Add to MusicBrainz**: If album doesn't exist, add it first

```bash
# Import with specific MusicBrainz release ID
beet import --search-id "release:12345678-1234-1234-1234-123456789012" /path
```

## Configuration for Docker

```yaml
# docker-compose volume mounts
volumes:
    - /path/to/music:/music
    - /path/to/config/beets:/config/beets

# Environment
environment:
    - BEETSDIR=/config/beets
```

Beets config at `/config/beets/config.yaml`:
```yaml
directory: /music/library
library: /config/beets/library.db
```
