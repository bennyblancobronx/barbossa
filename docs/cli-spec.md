# Barbossa CLI Specification

Version: 0.1.9

## Overview

The Barbossa CLI (`barbossa`) wraps the API for command-line access. Every CLI command maps to an API endpoint.

Downloads are a temporary staging area. Imported albums land in the master library.

```bash
barbossa [command] [subcommand] [options]
```

## Global Options

```bash
--api-url URL      API server URL (default: http://localhost:8080)
--token TOKEN      JWT token for authentication
--config FILE      Config file path (default: ~/.barbossa/config.yaml)
--format FORMAT    Output format: table, json, csv (default: table)
--quiet            Suppress non-essential output
--verbose          Enable debug output
--help             Show help
--version          Show version
```

## Authentication

```bash
# Login (saves token to config)
barbossa auth login
  Username: admin
  Password: ****
  Logged in successfully. Token saved.

# Check current user
barbossa auth whoami
  Logged in as: admin (admin)

# Logout
barbossa auth logout
  Logged out successfully.
```

---

## Library Commands

### List Artists

```bash
barbossa library artists [options]
  --letter LETTER    Filter by first letter (A-Z, #)
  --page N           Page number
  --limit N          Items per page

# Examples
barbossa library artists
barbossa library artists --letter P
barbossa library artists --format json
```

### List Albums

```bash
barbossa library albums [options]
  --artist ID        Filter by artist ID
  --user USERNAME    Show user's library only
  --page N           Page number

# Examples
barbossa library albums
barbossa library albums --artist 42
barbossa library albums --user dad
```

### Get Artist/Album/Track Details

```bash
barbossa library artist ID
barbossa library album ID
barbossa library track ID

# Examples
barbossa library artist 42
barbossa library album 123 --format json
```

### Search Library

```bash
barbossa library search QUERY [options]
  --type TYPE        artist, album, track, all (default: all)
  --limit N          Max results

# Examples
barbossa library search "pink floyd"
barbossa library search "dark side" --type album
```

### Delete (Admin Only)

```bash
barbossa library delete album ID [options]
  --force            Skip confirmation

# Prompts for confirmation unless --force
barbossa library delete album 123
  Delete "Pink Floyd - Dark Side of the Moon" from disk? [y/N]: y
  Deleted.
```

---

## User Library Commands (Hearts)

### Heart/Unheart Album

```bash
barbossa heart album ID [options]
  --user USERNAME    Target user (admin can specify, others use self)

barbossa unheart album ID [options]
  --user USERNAME

# Examples
barbossa heart album 123
barbossa heart album 123 --user kid
barbossa unheart album 123
```

### Heart/Unheart Track

```bash
barbossa heart track ID
barbossa unheart track ID

# Examples
barbossa heart track 456
```

### List User Library

```bash
barbossa library list [options]
  --user USERNAME    Target user (default: current user)

# Examples
barbossa library list
barbossa library list --user mom
barbossa library list --format json
```

---

## Download Commands

### Search Qobuz

```bash
barbossa download search qobuz QUERY --type TYPE
  --type TYPE        Required: artist, album, track, playlist
  --limit N          Max results (default: 20)

# Examples
barbossa download search qobuz "pink floyd" --type artist
barbossa download search qobuz "dark side of the moon" --type album
barbossa download search qobuz "comfortably numb" --type track
```

### Search Lidarr

```bash
barbossa download search lidarr QUERY

# Examples
barbossa download search lidarr "pink floyd"
```

### Download from Qobuz

```bash
barbossa download qobuz URL [options]
  --type TYPE        Optional: artist, album, track, playlist (for auto-heart rule)

# Examples
barbossa download qobuz "https://www.qobuz.com/us-en/album/..."
```

### Download from URL (YouTube, Bandcamp, etc.)

```bash
barbossa download url URL [options]
  --confirm-lossy    Required for lossy sources (YouTube, etc.)
  --type TYPE        Optional: artist, album, track, playlist (for auto-heart rule)

# Examples
barbossa download url "https://www.youtube.com/watch?v=..." --confirm-lossy
barbossa download url "https://artist.bandcamp.com/track/..." --confirm-lossy
```

### Request via Lidarr

```bash
barbossa download lidarr ARTIST_NAME [options]
  --mbid ID          MusicBrainz ID (optional)

# Examples
barbossa download lidarr "Pink Floyd"
```

### Download Queue

```bash
barbossa download queue [options]
  --watch            Watch for updates (live refresh)

# Examples
barbossa download queue
barbossa download queue --watch
```

### Cancel Download

```bash
barbossa download cancel ID

# Examples
barbossa download cancel 42
```

---

## Import Commands

### Scan Pending Imports

```bash
barbossa import scan

# Scans /music/import/pending and processes files
```

### List Pending Review

```bash
barbossa import review [options]
  --status STATUS    pending, approved, rejected

# Examples
barbossa import review
barbossa import review --status pending
```

### Approve/Reject Import

```bash
barbossa import approve ID [options]
  --artist NAME      Override artist name
  --album NAME       Override album name
  --year YEAR        Override year

barbossa import reject ID [options]
  --reason TEXT      Reason for rejection

# Examples
barbossa import approve 5
barbossa import approve 5 --artist "Pink Floyd" --album "The Wall"
barbossa import reject 6 --reason "Duplicate"
```

---

## Export Commands

### Export User Library

```bash
barbossa export [options]
  --user USERNAME    User to export (default: current)
  --dest PATH        Destination path (required)
  --format FORMAT    flac, mp3, both (default: flac)
  --artwork          Include artwork (default: true)
  --playlist         Generate M3U playlist

# Examples
barbossa export --dest /mnt/external/music --format flac
barbossa export --user kid --dest /mnt/usb --format mp3
barbossa export --dest /backup --format both --playlist
```

### Check Export Status

```bash
barbossa export status ID

# Examples
barbossa export status 3
```

---

## Admin Commands

### User Management

```bash
# List users
barbossa admin users

# Add user
barbossa admin users add USERNAME [options]
  --admin            Make user an admin
  --password PASS    Set password (prompts if not provided)

# Remove user
barbossa admin users remove USERNAME [options]
  --force            Skip confirmation

# Update user
barbossa admin users update USERNAME [options]
  --password PASS    New password
  --admin            Set admin status (true/false)

# Examples
barbossa admin users
barbossa admin users add kid
barbossa admin users add parent --admin
barbossa admin users remove kid --force
barbossa admin users update kid --password newpass
```

### Library Maintenance

```bash
# Full rescan
barbossa admin rescan

# Verify file integrity
barbossa admin integrity [options]
  --fix              Attempt to fix issues

# Find duplicates
barbossa admin dupes [options]
  --action ACTION    report, keep-best, interactive

# Examples
barbossa admin rescan
barbossa admin integrity
barbossa admin integrity --fix
barbossa admin dupes --action report
```

---

## TorrentLeech Commands (Admin Only)

### Check if Exists

```bash
barbossa tl check RELEASE_NAME

# Examples
barbossa tl check "Pink.Floyd.Dark.Side.of.the.Moon.1973.FLAC"
  Result: Not found (safe to upload)

barbossa tl check "Tool.Lateralus.2001.FLAC"
  Result: Found (duplicate exists)
```

### Upload Album

```bash
barbossa tl upload ALBUM_ID [options]
  --tags TAGS        Comma-separated tags
  --force            Skip existence check

# Examples
barbossa tl upload 123
barbossa tl upload 123 --tags "FLAC,Lossless,24bit"
```

---

## Integration Commands

### Lidarr

```bash
# Check connection
barbossa lidarr status

# View queue
barbossa lidarr queue

# Request artist
barbossa lidarr request ARTIST_NAME

# Examples
barbossa lidarr status
barbossa lidarr queue
barbossa lidarr request "Radiohead"
```

### Plex

```bash
# Check connection
barbossa plex status

# Trigger scan
barbossa plex scan [options]
  --path PATH        Scan specific path only

# Examples
barbossa plex status
barbossa plex scan
barbossa plex scan --path "/music/library/Pink Floyd"
```

### Bandcamp

```bash
# Sync purchased collection
barbossa bandcamp sync [options]
  --cookies FILE     Cookies file path

# Examples
barbossa bandcamp sync
barbossa bandcamp sync --cookies ~/bandcamp-cookies.txt
```

---

## Settings Commands

```bash
# View all settings
barbossa settings

# Get specific setting
barbossa settings get KEY

# Set value (admin only)
barbossa settings set KEY VALUE

# Examples
barbossa settings
barbossa settings get qobuz.quality
barbossa settings set qobuz.quality 4
barbossa settings set plex.auto_scan true
```

---

## Output Formats

### Table (Default)

```
ID    Artist       Album                    Year  Tracks
----  -----------  -----------------------  ----  ------
1     Pink Floyd   Dark Side of the Moon    1973  10
2     Pink Floyd   The Wall                 1979  26
```

### JSON

```bash
barbossa library albums --format json
```

```json
{
  "items": [
    {
      "id": 1,
      "artist": "Pink Floyd",
      "title": "Dark Side of the Moon",
      "year": 1973,
      "tracks": 10
    }
  ],
  "total": 2
}
```

### CSV

```bash
barbossa library albums --format csv
```

```csv
id,artist,title,year,tracks
1,Pink Floyd,Dark Side of the Moon,1973,10
2,Pink Floyd,The Wall,1979,26
```

---

## Configuration File

Location: `~/.barbossa/config.yaml`

```yaml
api_url: http://localhost:8080
token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
default_format: table
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Authentication required |
| 4 | Permission denied |
| 5 | Not found |
| 6 | Connection error |

---

## Command Reference (Quick)

```
barbossa auth login|logout|whoami

barbossa library artists|albums|search|artist|album|track|list|delete

barbossa heart album|track ID
barbossa unheart album|track ID

barbossa download search qobuz|lidarr QUERY
barbossa download qobuz|url|lidarr URL
barbossa download queue|cancel

barbossa import scan|review|approve|reject

barbossa export [--dest PATH --format FORMAT]

barbossa admin users|rescan|integrity|dupes

barbossa tl check|upload

barbossa lidarr status|queue|request
barbossa plex status|scan
barbossa bandcamp sync

barbossa settings [get|set KEY [VALUE]]
```
