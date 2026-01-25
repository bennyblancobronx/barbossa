# ExifTool Integration Guide

Research compiled from [exiftool.org](https://exiftool.org/), [FLAC Tags](https://exiftool.org/TagNames/FLAC.html), [ID3 Tags](https://www.exiftool.org/TagNames/ID3.html), and [PyExifTool](https://sylikc.github.io/pyexiftool/).

## Overview

ExifTool extracts metadata from audio files including technical quality data (sample rate, bit depth) that Barbossa uses for duplicate quality comparison. Supports FLAC, MP3, WAV, OGG, AIFF, M4A, and more.

## Installation

```bash
# macOS
brew install exiftool

# Ubuntu/Debian
sudo apt install libimage-exiftool-perl

# Windows
# Download from https://exiftool.org/

# Python library
pip install pyexiftool
```

## Audio Technical Tags

### FLAC StreamInfo Tags

| Tag Name | Description |
|----------|-------------|
| `SampleRate` | Sampling frequency (e.g., 44100, 96000, 192000) |
| `BitsPerSample` | Bit depth (e.g., 16, 24) |
| `Channels` | Number of audio channels |
| `TotalSamples` | Total sample count (for duration calculation) |
| `BlockSizeMin/Max` | Block size parameters |
| `FrameSizeMin/Max` | Frame size parameters |
| `MD5Signature` | Data integrity checksum |

### MP3/MPEG Audio Tags

| Tag Name | Description |
|----------|-------------|
| `AudioBitrate` | Bitrate in kbps (e.g., 320 kbps) |
| `SampleRate` | Sampling frequency (e.g., 44100) |
| `ChannelMode` | Stereo, Joint Stereo, Dual Channel, Mono |
| `MPEGAudioVersion` | MPEG version (1, 2, 2.5) |
| `AudioLayer` | Layer type (1, 2, 3) |
| `Duration` | Track duration (composite tag) |

### Common ID3 Tags (Descriptive)

| Tag Name | Description |
|----------|-------------|
| `Artist` | Track artist |
| `Album` | Album name |
| `Title` | Track title |
| `Year` | Release year |
| `Genre` | Music genre |
| `Track` | Track number |
| `BeatsPerMinute` | BPM/tempo |

## CLI Commands

### Extract All Metadata

```bash
# All tags with descriptions
exiftool audio.flac

# All tags with actual tag names (for scripting)
exiftool -s audio.flac

# All tags with group names
exiftool -G audio.flac
```

### Extract Specific Tags

```bash
# Quality-related tags for FLAC
exiftool -SampleRate -BitsPerSample -Channels -Duration audio.flac

# Quality-related tags for MP3
exiftool -AudioBitrate -SampleRate -ChannelMode -Duration audio.mp3

# Multiple files
exiftool -SampleRate -BitsPerSample *.flac
```

### JSON Output

```bash
# JSON format (for parsing)
exiftool -j audio.flac

# JSON with specific tags
exiftool -j -SampleRate -BitsPerSample -Channels audio.flac

# JSON with group names
exiftool -j -G audio.flac

# Pretty-printed JSON
exiftool -j -SampleRate -BitsPerSample audio.flac | python -m json.tool
```

### Batch Processing

```bash
# All FLAC files in directory
exiftool -j -SampleRate -BitsPerSample -Channels -ext flac /music/library/

# Recursive with subdirectories
exiftool -r -j -SampleRate -BitsPerSample -ext flac /music/library/

# Multiple extensions
exiftool -j -ext flac -ext mp3 -ext m4a /music/downloads/
```

### Example Output

```bash
$ exiftool -s -SampleRate -BitsPerSample -Channels -Duration audio.flac
SampleRate                      : 96000
BitsPerSample                   : 24
Channels                        : 2
Duration                        : 0:04:32
```

```bash
$ exiftool -j audio.flac
[{
  "SourceFile": "audio.flac",
  "SampleRate": 96000,
  "BitsPerSample": 24,
  "Channels": 2,
  "Duration": "0:04:32"
}]
```

## Python Integration (PyExifTool)

### Installation

```bash
pip install pyexiftool
```

Requires exiftool CLI installed on system (version 12.15+).

### Basic Usage

```python
from exiftool import ExifToolHelper

def get_audio_quality(file_path: str) -> dict:
    """Extract audio quality metadata from file."""
    with ExifToolHelper() as et:
        metadata = et.get_metadata(file_path)
        if metadata:
            return metadata[0]
    return {}

# Usage
quality = get_audio_quality("/music/library/Artist/Album/track.flac")
print(f"Sample Rate: {quality.get('FLAC:SampleRate')}")
print(f"Bit Depth: {quality.get('FLAC:BitsPerSample')}")
```

### Extract Specific Tags

```python
from exiftool import ExifToolHelper

def get_quality_tags(file_paths: list) -> list:
    """Extract quality-related tags from multiple files."""
    tags = [
        "SampleRate",
        "BitsPerSample",
        "Channels",
        "Duration",
        "AudioBitrate",
        "FileSize"
    ]

    with ExifToolHelper() as et:
        return et.get_tags(file_paths, tags=tags)

# Usage
files = ["/music/track1.flac", "/music/track2.flac"]
results = get_quality_tags(files)
for result in results:
    print(result)
```

### Batch Processing Directory

```python
from exiftool import ExifToolHelper
from pathlib import Path

def scan_library_quality(library_path: str) -> list:
    """Scan all audio files in library for quality data."""
    audio_extensions = {'.flac', '.mp3', '.m4a', '.wav', '.ogg'}

    # Collect all audio files
    files = []
    for ext in audio_extensions:
        files.extend(Path(library_path).rglob(f"*{ext}"))

    if not files:
        return []

    # Extract quality metadata
    with ExifToolHelper() as et:
        return et.get_tags(
            [str(f) for f in files],
            tags=["SampleRate", "BitsPerSample", "Channels", "Duration", "AudioBitrate"]
        )

# Usage
quality_data = scan_library_quality("/music/library")
for track in quality_data:
    print(f"{track['SourceFile']}: {track.get('FLAC:SampleRate', track.get('MPEG:SampleRate', 'N/A'))}")
```

### JSON Output via CLI

```python
from exiftool import ExifTool
import json

def get_metadata_json(file_path: str) -> dict:
    """Get metadata as JSON using low-level API."""
    with ExifTool() as et:
        result = et.execute_json(file_path)
        if result:
            return result[0]
    return {}
```

## Barbossa Integration

### Quality Comparison Logic

```python
from dataclasses import dataclass
from typing import Optional
from exiftool import ExifToolHelper

@dataclass
class AudioQuality:
    sample_rate: int
    bit_depth: int
    channels: int
    bitrate: Optional[int] = None
    file_size: int = 0

def extract_quality(file_path: str) -> AudioQuality:
    """Extract audio quality from file."""
    with ExifToolHelper() as et:
        data = et.get_tags(
            [file_path],
            tags=["SampleRate", "BitsPerSample", "Channels", "AudioBitrate", "FileSize"]
        )[0]

    return AudioQuality(
        sample_rate=data.get("FLAC:SampleRate") or data.get("MPEG:SampleRate") or 0,
        bit_depth=data.get("FLAC:BitsPerSample") or 16,  # MP3 is effectively 16-bit
        channels=data.get("FLAC:Channels") or data.get("MPEG:Channels") or 2,
        bitrate=data.get("MPEG:AudioBitrate"),
        file_size=data.get("File:FileSize") or 0
    )

def is_higher_quality(new: AudioQuality, existing: AudioQuality) -> bool:
    """Determine if new file is higher quality than existing."""
    # Higher sample rate is better
    if new.sample_rate > existing.sample_rate:
        return True
    if new.sample_rate < existing.sample_rate:
        return False

    # Same sample rate: higher bit depth is better
    if new.bit_depth > existing.bit_depth:
        return True
    if new.bit_depth < existing.bit_depth:
        return False

    # Same sample rate and bit depth: larger file might be better
    # (less compression, more detail)
    if new.file_size > existing.file_size * 1.1:  # 10% larger
        return True

    return False
```

### Duplicate Detection Integration

```python
def check_duplicate_quality(
    new_file: str,
    existing_file: str
) -> tuple[bool, str]:
    """
    Check if new file is duplicate and compare quality.

    Returns:
        (should_replace, reason)
    """
    new_quality = extract_quality(new_file)
    existing_quality = extract_quality(existing_file)

    if is_higher_quality(new_quality, existing_quality):
        reason = (
            f"New file is higher quality: "
            f"{new_quality.sample_rate/1000}kHz/{new_quality.bit_depth}bit vs "
            f"{existing_quality.sample_rate/1000}kHz/{existing_quality.bit_depth}bit"
        )
        return True, reason
    else:
        reason = (
            f"Existing file is same or higher quality: "
            f"{existing_quality.sample_rate/1000}kHz/{existing_quality.bit_depth}bit"
        )
        return False, reason
```

### Database Schema for Quality Data

```sql
CREATE TABLE track_quality (
    track_id INTEGER PRIMARY KEY REFERENCES tracks(id),
    sample_rate INTEGER,       -- e.g., 44100, 96000, 192000
    bit_depth INTEGER,         -- e.g., 16, 24
    channels INTEGER,          -- e.g., 2
    bitrate INTEGER,           -- kbps for lossy formats
    file_size INTEGER,         -- bytes
    format VARCHAR(10),        -- FLAC, MP3, etc.
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for quality comparisons
CREATE INDEX idx_track_quality_sample_rate ON track_quality(sample_rate);
CREATE INDEX idx_track_quality_bit_depth ON track_quality(bit_depth);
```

### Import Pipeline Integration

```python
def import_with_quality_check(download_path: str, master_library: str):
    """
    Import downloaded album with quality-aware duplicate detection.

    1. Extract quality data from downloaded files
    2. Check for existing tracks in library
    3. Compare quality if duplicates found
    4. Keep higher quality version
    5. Run beets import
    """
    from pathlib import Path

    downloaded_files = list(Path(download_path).glob("*.flac"))

    for file in downloaded_files:
        quality = extract_quality(str(file))

        # Check database for existing track with same artist/album/title
        existing = find_existing_track(file)

        if existing:
            should_replace, reason = check_duplicate_quality(
                str(file),
                existing.path
            )

            if should_replace:
                log.info(f"Replacing {existing.path}: {reason}")
                remove_track(existing)
            else:
                log.info(f"Skipping {file.name}: {reason}")
                continue

        # Proceed with beets import
        run_beets_import(download_path)
```

## Quality Tiers Reference

| Sample Rate | Bit Depth | Quality Level | Source |
|-------------|-----------|---------------|--------|
| 44100 | 16 | CD Quality | CD, Standard streaming |
| 48000 | 16 | DVD Quality | DVD-Audio |
| 48000 | 24 | HD | Studio masters |
| 88200 | 24 | Hi-Res | 2x CD sample rate |
| 96000 | 24 | Hi-Res | Common hi-res standard |
| 176400 | 24 | Ultra Hi-Res | 4x CD sample rate |
| 192000 | 24 | Ultra Hi-Res | Maximum Qobuz quality |

### Quality Comparison Priority

1. **Sample Rate** - Higher is better (192kHz > 96kHz > 44.1kHz)
2. **Bit Depth** - Higher is better (24-bit > 16-bit)
3. **Format** - Lossless preferred (FLAC > MP3)
4. **File Size** - For same format/specs, larger may indicate less compression

## Useful Commands Reference

```bash
# Show all available tags for a file
exiftool -s -G audio.flac

# List all FLAC-specific tags
exiftool -FLAC:all audio.flac

# List all MPEG-specific tags (MP3)
exiftool -MPEG:all audio.mp3

# List all ID3 tags
exiftool -ID3:all audio.mp3

# Compare two files
exiftool -s -SampleRate -BitsPerSample file1.flac file2.flac

# Recursive JSON dump of library
exiftool -r -j -SampleRate -BitsPerSample -Channels -ext flac /music/ > library_quality.json
```
