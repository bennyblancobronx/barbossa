# Barbossa

A family-oriented web app for managing a centralized music library with per-user collections. Downloads hi-res music from multiple sources, organizes for Plex, and lets each family member curate and export their own library.

## What Barbossa Is

- **Multi-Source Download Manager**: Qobuz (primary), Lidarr (automated), yt-dlp (fallback)
- **Library Organizer**: Beets for metadata, Plex-compatible naming
- **Per-User Collections**: Each user has their own "My Library" via symlinks
- **Quality Tracker**: ExifTool extracts sample rate/bit depth for dupe comparison
- **Long-Term Archive**: Export, backup, integrity verification
- **Admin Tools**: TorrentLeech upload, user management, library health

## What Barbossa Is NOT

- NOT a music player/streamer (use Plex/Plexamp for that)
- NOT replacing your existing music server
- NOT a Spotify/Apple Music clone

## How It Works

```
User browses Barbossa --> Searches for music
                                |
          +---------+-----------+-----------+
          |         |           |           |
       Qobuz     Lidarr     YouTube     Import
      (24/192)  (Usenet)    (lossy)    (CD rips)
          |         |           |           |
          +---------+-----------+-----------+
                         |
                         v
              Beets processes metadata + naming
                         |
                         v
              ExifTool extracts quality data
                         |
                         v
              Quality comparison (keep best)
                         |
                         v
              Album appears in Master Library
                         |
                         v
          User hearts album --> Symlink in User Library
                         |
                         v
              Plex sees it --> Available in Plexamp
```

## Download Source Priority

| Priority | Source | Max Quality | Use Case |
|----------|--------|-------------|----------|
| 1 | Qobuz (streamrip) | 24-bit/192kHz | Primary, mainstream catalog |
| 2 | Lidarr (Usenet/Torrent) | 24-bit/96kHz typical | Automated, rare releases |
| 3 | Manual Import | Variable | CD rips, Bandcamp, purchases |
| 4 | yt-dlp (YouTube) | ~256kbps lossy | Live recordings, unreleased |

## Tech Stack

- **Backend**: Python (FastAPI)
- **Frontend**: React or Vue
- **Database**: PostgreSQL
- **Queue**: Redis + Celery
- **Container**: Docker
- **External Tools**: streamrip, beets, exiftool, yt-dlp
- **External Services**: Lidarr (API), Plex (API), TorrentLeech (API)

## Core Features

1. **Master Library** - Browse all music in the collection
2. **User Library** - Browse only your hearted music (symlinks)
3. **Downloads** - Multi-source: Qobuz, Lidarr request, YouTube fallback
4. **Import** - Watch folder for CD rips, purchases, existing collections
5. **Export** - Full quality FLAC or MP3 for portability
6. **Settings** - Library paths, users, source configs (admin only)
7. **Activity Log** - Track who added what, when
8. **Backup** - Local, NAS, or cloud backup destinations

## Family Archive Features

- **Per-User Export**: Family member moves out, takes their collection
- **Source Tracking**: Know where every track came from
- **Quality Preservation**: Always keep the best version
- **Integrity Checks**: Detect bit rot before it's too late
- **Incomplete Album Handling**: Fill gaps from multiple sources
- **Review Queue**: Manual approval for unidentified imports
