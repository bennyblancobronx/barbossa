# Changelog

## [0.1.144] - 2026-01-28

### TL;DR
- Add explicit `trusted` flag to import pipeline so Qobuz is never punished by validation gates
- Skip strict metadata validation and redundant import_service validation for trusted sources
- Use Qobuz API metadata as fallback when MusicBrainz identify fails (MB down, album not in MB, etc.)
- Fall back to direct file move when beets crashes on trusted source (files are good, only beets failed)
- Fix Celery retrying NeedsReviewError/DuplicateError 3 times instead of treating them as terminal states
- Fix "Destination path already exists" crash when moving to review folder (rmtree silent failure caused nested paths)
- Fix "Could not find imported album" after beets --move by capturing track filenames before move
- Show actual review reason in Downloads UI instead of hardcoded "low confidence match"

## [0.1.143] - 2026-01-28

### TL;DR
- Fix download count badge in sidebar not updating in real time
- Badge now reacts instantly to new downloads, completions, and failures via WebSocket
- Download store is populated on WebSocket connect (not just when Downloads page is mounted)
- Backend now broadcasts download:queued event when new downloads are created
- Backend now broadcasts download:error on Celery task max retry failure
- Prevent duplicate WebSocket connections when connectWebSocket is called multiple times
- Prevent duplicate download entries in store when WS event and API response race

## [0.1.142] - 2026-01-28

### TL;DR
- Install `flac` package in Docker image for FLAC integrity verification
- Fix Qobuz URL regex to handle alphanumeric album IDs (not just numeric)
- Prevent duplicate folder accumulation: review and failed folders now replace instead of appending `_1`, `_2` suffixes
- Add staging folder cleanup to maintenance task: stale downloads/review/failed files older than 7 days are auto-removed
- Cleaned 18 stale staging folders from disk

## [0.1.141] - 2026-01-28

### TL;DR
- Fix false positive "album title matches folder name" validation error after beets import (beets names folders from album tag, so they always match)
- Only flag when album title also matches track title (indicating genuinely missing tags)

## [0.1.140] - 2026-01-28

### TL;DR
- Fix `_find_imported_path()` failing when beets replaces special chars with underscores (e.g. "i am  i was" -> "i am _ i was")
- Fix `_detect_compilation()` not catching albums where albumartist tag is "Various Artists" but track artists are mostly the same (e.g. film scores)
- Both fixes required for compilation and non-standard-named albums to import successfully

## [0.1.139] - 2026-01-28

### TL;DR
- Fix "'float' object has no attribute 'lower'" at root cause: exiftool `-n` flag returns numeric values for text tags (artist, album, title, genre, composer, label)
- Guard `normalize_text()` against non-string input
- Guard exiftool metadata extraction with `str()` cast on all text fields
- Docker rebuild required

## [0.1.138] - 2026-01-28

### TL;DR
- Additional str() guards in import_service.py for metadata artist values

## [0.1.137] - 2026-01-28

### TL;DR
- Fix compilation album imports (soundtracks, VA compilations) failing with "Could not find imported album"
- Pipeline now checks beets Compilations/ folder, allows "various artists" for real compilations, and auto-assigns "Soundtrack" or "Compilations" as artist name

## [0.1.136] - 2026-01-28

### TL;DR
- Fix Docker boot failure after reboot (nginx crash loop, cascading dependency failure)
- Make Docker setup portable for deployment on other devices

### Changed
- **docker-compose.yml**: Remove obsolete `version` key. All services now use `depends_on` with `condition: service_healthy` so nothing starts until its dependencies are actually ready. Ports configurable via .env (API_PORT, FRONTEND_PORT). Added CORS_ORIGINS passthrough. Bumped API healthcheck to 5 retries with 60s start period.
- **frontend/nginx.conf**: Use Docker DNS resolver (127.0.0.11) and variable-based upstream (`set $backend`) so nginx resolves at request time, not startup. This fixes the fatal crash when the API container is not yet running. Added proxy headers and timeouts.
- **backend/Dockerfile**: Added entrypoint script for auto DB table creation on first boot. Removed `--reload` (dev-only). Added directory structure creation for /music subdirs. Stopped copying tests into image.

### Added
- **backend/entrypoint.sh**: Runs DB table verification before API startup, skipped for worker/beat/watcher processes.
- **backend/.dockerignore**: Excludes __pycache__, tests, .env, venv from image builds.
- **frontend/.dockerignore**: Excludes node_modules, build artifacts from context.
- **backend/db/init/001_schema.sql**: DB init script for fresh postgres containers (first-run only).

---

## [0.1.135] - 2026-01-26

### TL;DR
- Show active download count badge in nav bar
- Move search bar to bottom of sidebar

### Changed
- **components/Sidebar.jsx**: Add download count badge next to "Downloads" nav link
- **components/Sidebar.jsx**: Move search bar to bottom of sidebar (above footer)
- **styles/design-system.css**: Add `.nav-badge` and `.sidebar-bottom` styles

---

## [0.1.134] - 2026-01-26

### TL;DR
- Add failed downloads section with error reasons in Downloads page
- Failed downloads now show separately with retry/dismiss options

### Added
- **pages/Downloads.jsx**: Failed downloads section showing error reasons
  - Separate section for failed downloads with error messages
  - Retry button to restart failed downloads
  - Dismiss button to remove failed entries
  - Timestamp of when download failed
- **api/downloads.py**: POST /downloads/{id}/retry endpoint to retry failed downloads
- **api/downloads.py**: Include failed downloads in queue response
- **services/api.js**: retryDownload() and dismissDownload() API functions
- **styles/design-system.css**: Styling for failed downloads section

---

## [0.1.133] - 2026-01-26

### TL;DR
- Fix SMB mount deletion: files now delete properly on network shares
- Fix deletion redirect: page navigates to artist list after deletion
- Root cause: SMB creates locked .smbdelete files that blocked shutil.rmtree

### Fixed
- **services/library.py**: SMB-safe deletion with smb_safe_rmtree() function
  - Retries deletion with exponential backoff for SMB lock issues
  - Handles "Device or resource busy" and "Directory not empty" errors
  - Proceeds with database deletion even if SMB files are pending
  - Detects directories with only .smbdelete files (already pending deletion)
- **pages/Library.jsx**: Navigate back to artist list when deleting artist from album view
- **pages/Library.jsx**: Navigate back to artist list when deleting last album
- **pages/UserLibrary.jsx**: Same navigation fixes for My Library page
- **components/ArtistCard.jsx**: Show alert on delete failure instead of silent fail
- **components/AlbumCard.jsx**: Show alert on delete failure instead of silent fail

### Root Cause
SMB protocol renames files to .smbdeleteXXXXX before deletion, but keeps them locked
until the server releases them. shutil.rmtree() failed with "Device or resource busy"
when trying to delete these locked files, causing the entire deletion to abort.

---

## [0.1.132] - 2026-01-26

### TL;DR
- Fix enrichment API async/sync execution issues

### Fixed
- **api/enrichment.py**: Use await instead of asyncio.run_until_complete for sync mode
- **services/enrichment.py**: Convert album.tracks to list before iterating (lazy loading fix)

---

## [0.1.131] - 2026-01-26

### TL;DR
- Phase 8 enhancements: REST API, scheduled task, auto-enrich on import

### Added
- **api/enrichment.py**: REST API endpoints for enrichment
  - GET /enrichment/stats - get enrichment statistics
  - POST /enrichment/album/{id} - enrich album lyrics
  - POST /enrichment/track/{id} - enrich single track
  - POST /enrichment/batch - batch enrich missing lyrics
  - GET /enrichment/tracks/missing-lyrics - list tracks without lyrics
- **worker.py**: Weekly scheduled task "enrich-missing-lyrics" (Saturdays 2 AM, 500 tracks)
- **services/import_service.py**: enrich_on_import parameter (default True)
  - Automatically triggers lyrics enrichment after successful import

### Changed
- **api/__init__.py**: Added enrichment router
- **worker.py**: Added app.tasks.enrichment to include list
- **worker.py**: Added enrichment task routing to maintenance queue

---

## [0.1.130] - 2026-01-26

### TL;DR
- Phase 8 complete: Post-import enrichment pipeline with lyrics fetching

### Added
- **services/enrichment.py**: New EnrichmentService for post-import metadata enrichment
- **services/enrichment.py**: fetch_lyrics_lrclib() - fetches lyrics from LRCLIB.net (free, no API key)
- **services/enrichment.py**: enrich_track_lyrics() - enriches single track with lyrics
- **services/enrichment.py**: enrich_album_lyrics() - enriches all tracks in an album
- **services/enrichment.py**: enrich_missing_lyrics() - batch enrich tracks missing lyrics
- **services/enrichment.py**: get_enrichment_stats() - statistics for missing metadata
- **tasks/enrichment.py**: Celery tasks for background enrichment
- **tasks/enrichment.py**: enrich_album_lyrics_task - background album lyrics enrichment
- **tasks/enrichment.py**: enrich_missing_lyrics_task - batch background enrichment
- **tasks/enrichment.py**: enrich_track_lyrics_task - single track enrichment
- **tasks/enrichment.py**: get_enrichment_stats_task - get enrichment statistics

### Enrichment Service Features
- LRCLIB.net integration (free lyrics API, no API key required)
- Supports exact match and fuzzy search fallback
- Rate limiting with 0.5s delay between requests
- Returns both enriched count and per-track results
- Statistics endpoint shows lyrics coverage percentage

---

## [0.1.129] - 2026-01-26

### TL;DR
- Phase 7 complete: Qobuz metadata enrichment (label, genre, UPC, ISRC)

### Added
- **services/download.py**: _merge_qobuz_metadata() - merges Qobuz API data with track metadata
- **services/download.py**: _fetch_qobuz_album_metadata() - fetches album details from Qobuz API before import
- **integrations/qobuz_api.py**: _parse_album() now includes UPC and release_date fields
- **integrations/qobuz_api.py**: _parse_track() now includes ISRC and explicit fields

### Changed
- **services/download.py**: download_qobuz() now pre-fetches Qobuz metadata before downloading
- **services/download.py**: _import_album() accepts qobuz_metadata parameter for enrichment
- **services/import_service.py**: import_album() now stores UPC from merged Qobuz data
- **services/import_service.py**: replace_album() now updates UPC if not already set

### Qobuz Metadata Enrichment Flow
1. Before download: fetch album details from Qobuz API
2. Extract: label, genre, UPC, explicit flag, per-track ISRC
3. After beets merge: merge Qobuz data (Qobuz is authoritative for these fields)
4. Store in database: album.upc, album.label, album.genre, track.isrc, track.explicit

---

## [0.1.128] - 2026-01-26

### TL;DR
- Maintenance task now uses BLAKE3 and FLAC stream verification

### Fixed
- **tasks/maintenance.py**: verify_integrity() now uses BLAKE3 via generate_checksum() instead of inline SHA-256
- **tasks/maintenance.py**: verify_integrity() now includes FLAC stream verification via IntegrityService

### Changed
- **tasks/maintenance.py**: Added include_flac_stream parameter to verify_integrity() (default True)
- **tasks/maintenance.py**: Moved _get_event_loop() to module level for reuse
- **tasks/maintenance.py**: Removed duplicate asyncio import from scan_library()

### Integrity Check Enhancements
- Checksum verification uses BLAKE3 (3-5x faster than SHA-256)
- FLAC files verified with `flac -t` for frame CRC and embedded MD5 checks
- NO_MD5 status tracked separately (typical for Qobuz files)
- Returns flac_verified and flac_no_md5 counts in result

---

## [0.1.127] - 2026-01-26

### TL;DR
- Phase 6 complete: File integrity verification via flac -t

### Added
- **services/integrity.py**: New IntegrityService for file verification
- **services/integrity.py**: verify_flac() - uses `flac -t` for FLAC stream testing
- **services/integrity.py**: verify_album() - verifies all audio files in directory
- **services/integrity.py**: IntegrityStatus enum (OK, FAILED, SKIPPED, NO_MD5, ERROR)
- **services/integrity.py**: IntegrityResult and AlbumIntegrityResult dataclasses

### Changed
- **services/import_service.py**: Added verify_integrity parameter (default True)
- **services/import_service.py**: Integrity check runs after content dupe check, before metadata validation
- **services/import_service.py**: Failed integrity raises ImportError with details
- **services/import_service.py**: Missing MD5 (Qobuz) logged as debug, not error (INT-004)

### Integrity Check Flow
1. After checksum generation and content dupe check
2. Run `flac -t` on all FLAC files
3. If FAILED: raise ImportError (corrupted files)
4. If NO_MD5: log debug (typical for Qobuz, frame CRCs still verified)
5. If ERROR: log warning (flac not installed), continue import

---

## [0.1.126] - 2026-01-26

### TL;DR
- Phase 5 caller integration: DuplicateContentError now handled in download, watcher, tasks

### Fixed
- **services/download.py**: Import DuplicateContentError and handle in both download_qobuz() and download_url()
- **watcher.py**: Import DuplicateContentError and handle before generic Exception handler
- **tasks/imports.py**: Import DuplicateContentError and handle in both process_import() and process_review()

### Behavior Change
- Content duplicates now properly set status=DUPLICATE instead of FAILED
- Content duplicates now link to existing album ID for user reference
- Watcher moves content duplicates to review queue with descriptive note

---

## [0.1.125] - 2026-01-26

### TL;DR
- Phase 5 complete: Content-based deduplication via BLAKE3 checksums

### Added
- **services/import_service.py**: DuplicateContentError exception for content duplicate detection
- **services/import_service.py**: find_duplicate_by_checksum() - finds existing albums by track checksums
- **services/import_service.py**: find_all_duplicate_tracks() - returns all tracks matching given checksums
- **services/import_service.py**: generate_track_checksums() - pre-computes checksums for all audio files
- **services/import_service.py**: compare_duplicate_quality() - compares quality of new vs existing album
- **services/import_service.py**: AUDIO_EXTENSIONS constant for audio file detection

### Changed
- **services/import_service.py**: import_album() now generates checksums FIRST (before DB operations)
- **services/import_service.py**: import_album() checks content duplicates BEFORE metadata duplicates
- **services/import_service.py**: import_album() uses pre-computed checksums for efficiency
- **services/import_service.py**: import_album() adds check_content_dupe parameter (default True)

### Content-Based Deduplication Flow
1. Generate BLAKE3 checksums for all tracks upfront
2. Query database for matching checksums
3. If match found, raise DuplicateContentError (caller decides: replace/skip/review)
4. compare_duplicate_quality() helps decide based on sample rate/bit depth

---

## [0.1.124] - 2026-01-26

### TL;DR
- Phase 4 complete: Artist metadata (country from MusicBrainz, biography from Qobuz)

### Changed
- **services/download.py**: _merge_beets_identification() now passes artist_country from MusicBrainz
- **services/import_service.py**: import_album() now passes country to _get_or_create_artist()
- **services/import_service.py**: fetch_artist_image_from_qobuz() now also stores artist biography
- **watcher.py**: merge_beets_identification() now passes artist_country
- **tasks/imports.py**: merge_beets_identification() now passes artist_country

### Artist Metadata Now Captured
- biography: From Qobuz API (stored when fetching artist image)
- country: From MusicBrainz via beets (ISO 3166-1 alpha-2 code)

---

## [0.1.123] - 2026-01-26

### TL;DR
- Phase 3 complete: Beets integration now returns full MusicBrainz data and merges with ExifTool metadata

### Changed
- **integrations/beets.py**: _identify_api() now returns musicbrainz_album_id, musicbrainz_artist_id, musicbrainz_release_group_id
- **integrations/beets.py**: _identify_api() now returns label, catalog_number, country, release_type, media, disctotal
- **integrations/beets.py**: _identify_api() now returns track_data with per-track MusicBrainz IDs and ISRC
- **integrations/beets.py**: _identify_cli() and _parse_folder_name() return consistent fields for fallback cases
- **services/download.py**: Added _merge_beets_identification() to merge beets MB data with ExifTool metadata
- **watcher.py**: Added merge_beets_identification() helper and integrated into import flow
- **tasks/imports.py**: Added merge_beets_identification() helper and integrated into run_import and process_review

### Beets Identification Now Returns
- Album: musicbrainz_album_id, musicbrainz_artist_id, musicbrainz_release_group_id, label, catalog_number, country, release_type
- Track (via track_data): musicbrainz_track_id, musicbrainz_recording_id, isrc, track_number, disc_number

---

## [0.1.122] - 2026-01-26

### TL;DR
- Phase 2+3+4 complete: ExifTool metadata extraction and import_service now capture all extended metadata

### Changed
- **integrations/exiftool.py**: Added 20+ new tags (ISRC, Composer, Lyrics, MusicBrainz IDs, Label, etc.)
- **integrations/exiftool.py**: Added _normalize_metadata() with format prefix handling (FLAC:, ID3:, Vorbis:)
- **integrations/exiftool.py**: Added _normalize_isrc() for standard ISRC format validation
- **integrations/exiftool.py**: Added _parse_track_number() and _parse_disc_number() for "3/12" format handling
- **services/import_service.py**: import_album() now stores genre, label, catalog_number, musicbrainz_id on Album
- **services/import_service.py**: import_album() now stores lyrics, isrc, composer, explicit, musicbrainz_id on Track
- **services/import_service.py**: Added _calculate_disc_count() helper
- **services/import_service.py**: Added _detect_compilation() helper (>3 unique artists = compilation)
- **services/import_service.py**: _get_or_create_artist() now accepts and stores MusicBrainz ID
- **services/import_service.py**: replace_album() now includes extended track metadata

### Metadata Now Captured
- Album: genre, label, catalog_number, musicbrainz_id, disc_count, is_compilation
- Track: lyrics, isrc, composer, explicit, musicbrainz_id
- Artist: musicbrainz_id (when available from embedded tags)

---

## [0.1.121] - 2026-01-26

### TL;DR
- Phase 1 complete: Database schema for extended metadata (4 migrations, 4 models updated)

### Added
- **Migration 014**: Track columns - isrc (indexed), composer, explicit
- **Migration 015**: Artist columns - biography, country
- **Migration 016**: Album columns - upc (indexed), release_type
- **Migration 017**: ImportHistory checksum column (indexed) for content-based dedup

### Changed
- **models/track.py**: Added isrc, composer, explicit columns
- **models/artist.py**: Added biography, country columns
- **models/album.py**: Added upc, release_type columns
- **models/import_history.py**: Added checksum column

---

## [0.1.120] - 2026-01-26

### TL;DR
- Complete metadata implementation plan with industry best practices research; 40+ implementation items

### Research Added (Part 8 of audit-014)
- **DDEX Standards**: ERN 4.3.x format, ISRC/ISWC/UPC hierarchy
- **Tagging Standards**: Vorbis Comments for FLAC (never ID3), ID3v2.4 for MP3
- **Tag Mapping**: Full Vorbis-to-ID3-to-DB column mapping from Picard docs
- **FLAC Integrity**: Native MD5 in STREAMINFO, Qobuz files missing MD5 (known issue)
- **Deduplication Strategy**: File hash > Audio hash > Fingerprint > Metadata (in order)

### Implementation Guides Added
- **8.7**: ExifTool extraction with _normalize_metadata() and _normalize_isrc()
- **8.8**: Beets integration returning full MusicBrainz data + track-level IDs
- **8.9**: Content-based deduplication with quality comparison
- **8.10**: FLAC integrity verification service using flac -t

### Checklist Expanded
- 8 phases, 35+ implementation items (DB-001 to OPT-004)
- Validation checklist for testing completeness
- Sources linked for all research

### Planned (Part 7 of audit-014)
- **Migrations 014-017**: track columns, artist columns, album columns, import_history index
- **ExifTool extraction**: Genre, Lyrics, ISRC, Composer, Label, MusicBrainz IDs
- **Import service**: Content-based dedup, compilation detection, disc_count
- **Beets integration**: Return MusicBrainz album/track/artist IDs
- **Qobuz capture**: Label, genre, UPC, ISRC per track
- **Integrity service**: FLAC MD5 verification (optional, warns on Qobuz)

---

## [0.1.119] - 2026-01-26

### TL;DR
- Comprehensive metadata audit documented; switched to BLAKE3 hashes for faster checksums

### Added
- **docs/audit-014-metadata-integrity.md**: Full audit checklist with 40+ items
- **services/quality.py**: `verify_checksum()` helper function
- **requirements.txt**: blake3==0.4.1 package

### Changed
- **services/quality.py**: `generate_checksum()` now uses BLAKE3 (3-5x faster than SHA-256)
- BLAKE3 falls back to SHA-256 if package not installed

### Documented
- Metadata capture gaps: genre, label, musicbrainz_id, lyrics not being stored
- Content-based dedup not implemented (checksums stored but not compared)
- ExifTool tags to add: ISRC, Composer, Label, MusicBrainzAlbumId, etc.
- Coding guide for new developers added to audit doc

---

## [0.1.118] - 2026-01-26

### TL;DR
- Root cause analysis: Added metadata validation to prevent "Unknown Artist" and "Track 01" imports

### Added
- **import_service.py**: `validate_metadata()` function with strict validation rules
- **import_service.py**: `MetadataValidationError` exception for failed validation
- **import_service.py**: `INVALID_ARTIST_PATTERNS` and `INVALID_TRACK_PATTERNS` constants

### Changed
- **import_service.py**: `import_album()` now validates metadata before import (default: strict=True)
- **download.py**: Pre-validates metadata before beets import, routes failures to review queue
- **download.py**: `_move_to_review()` now accepts `note` parameter for validation failure details
- **watcher.py**: Pre-validates metadata before auto-import
- **tasks/imports.py**: Pre-validates metadata before celery task import

### Root Cause Analysis
- **Why "Unknown Artist" from Qobuz**: Qobuz downloads bypassed confidence check (min_confidence=0.0), and metadata fallback was silent
- **Why "Track 01" names**: Direct fallback to generic names with no validation
- **Why MusicBrainz didn't catch it**: Lookup requires existing metadata; skipped if tags missing
- **Fix**: Validation now rejects invalid patterns before import, routes to review queue with specific failure reason

---

## [0.1.117] - 2026-01-26

### TL;DR
- Added track-level de-dupe protection after Deltron 3030 duplicate tracks investigation

### Added
- **alembic/versions/013_track_unique_constraint.py**: Unique constraint on (album_id, disc_number, track_number)
- **models/track.py**: Added UniqueConstraint to prevent duplicate track positions

### Fixed
- Deltron 3030 album: Removed 6 duplicate track records and files
- Duplicate album "I Hope You're Happy" by Blue October cleaned up

---

## [0.1.116] - 2026-01-26

### TL;DR
- Implemented all 3 library sync fixes: artist auto-heart, master library updates, de-dupe constraint

### Added
- **alembic/versions/011_user_artists.py**: Migration for user_artists table
- **alembic/versions/012_album_unique_constraint.py**: Migration for de-dupe constraint
- **models/user_artists.py**: New model for persistent artist subscriptions
- **import_service.py**: `auto_heart_for_followers()` method for auto-adding new albums

### Changed
- **models/album.py**: Added UniqueConstraint on (artist_id, normalized_title)
- **user_library.py**: `heart_artist()` now persists to user_artists table with auto_add_new flag
- **user_library.py**: `unheart_artist()` removes from user_artists table
- **user_library.py**: Added `get_users_following_artist()` and `is_following_artist()` methods
- **import_service.py**: Added IntegrityError handling for de-dupe race condition
- **tasks/imports.py**: Added broadcast_library_update and auto_heart_for_followers calls
- **watcher.py**: Added broadcast_library_update and auto_heart_for_followers calls

### Fixed
- Artist auto-heart now subscribes user to future albums from that artist
- Master library updates now broadcast to all connected clients
- De-dupe race condition prevented by database constraint

---

## [0.1.115] - 2026-01-26

### TL;DR
- Audit: documented 3 bugs in library sync system (artist auto-heart, master library updates, de-dupe race condition)

### Added
- **docs/bugfix-spec-011-library-sync.md**: Full spec for fixing:
  1. Artist auto-heart not adding future albums to user libraries
  2. Master library broadcast_library_update() never called
  3. De-dupe race condition allows duplicate album imports

---

## [0.1.114] - 2026-01-26

### TL;DR
- Qobuz artist page: added popularity sort and explicit-only filter

### Added
- **qobuz_api.py**: Capture `popularity` and `parental_warning` fields from Qobuz API
- **qobuz.py**: Added `popularity` and `explicit` fields to AlbumResult schema
- **qobuz.py**: Added `explicit_only` query param and `popularity` sort option to artist endpoint
- **QobuzArtist.jsx**: Added "Most Popular" sort option and "Explicit Only" checkbox
- **api.js**: Updated `getQobuzArtist` to pass `explicitOnly` parameter

---

## [0.1.113] - 2026-01-26

### TL;DR
- Added sync method to retroactively auto-heart albums with all tracks hearted

### Added
- **user_library.py**: `sync_auto_heart_albums()` method to fix existing data
- Ran sync for all users - 1 album auto-hearted for bryant

---

## [0.1.112] - 2026-01-26

### TL;DR
- Auto-heart album when all its tracks are individually hearted

### Added
- **user_library.py**: `_check_auto_heart_album()` method checks if all tracks on album are hearted
- When user hearts the final track on an album, album is automatically hearted too

---

## [0.1.111] - 2026-01-26

### TL;DR
- Track row height adjusted to Braun spec (52px) making icons appear proportionally larger

### Fixed
- **design-system.css**: Changed `--row-height` from 56px to 52px per Braun data table spec
- Track row heart and play icons (32px xl) now appear more prominent with tighter row height

---

## [0.1.110] - 2026-01-26

### TL;DR
- Fixed API bug where all albums showed as hearted in User Library artist view

### Fixed
- **library.py**: `get_user_library_artist_albums()` now uses `a.is_hearted` from service instead of hardcoded `True`

### Audit Results
Verified with database containing:
- User 2 has hearted album "Add Violence" (Nine Inch Nails)
- User 2 has hearted tracks from "With Teeth" and "Growin' Pains"

API now correctly returns:
- Add Violence: `is_hearted=true` (album directly hearted)
- With Teeth: `is_hearted=false` (appears because contains hearted track)
- Growin' Pains: `is_hearted=false` (appears because contains hearted track)

---

## [0.1.109] - 2026-01-26

### TL;DR
- User Library now shows artists/albums with ANY hearted content (albums OR individual tracks)

### Fixed
- **user_library.py**: `get_library_artists()` now includes artists with hearted TRACKS, not just hearted albums
- **user_library.py**: `get_library_artist_albums()` now includes albums containing hearted tracks
- **user_library.py**: `is_artist_hearted()` and `get_hearted_artist_ids()` check both albums and tracks

### Example
If you heart just ONE song from an album:
- That artist now appears in User Library Artists
- That album now appears under that artist
- The album shows the tracks (with heart status per-track)

This matches the expected hierarchy: Artist -> Album -> Tracks, regardless of whether you hearted the full album or individual tracks.

---

## [0.1.108] - 2026-01-26

### TL;DR
- User Library now mirrors Master Library hierarchy: Artists -> Albums -> Tracks

### Changed
- **UserLibrary.jsx**: Rewritten to match Master Library structure (no more separate Tracks view)
- **user_library.py**: Added `get_library_artists()` and `get_library_artist_albums()` methods
- **library.py**: Added `/me/library/artists` and `/me/library/artists/{id}/albums` endpoints
- **api.js**: Added `getUserLibraryArtists()` and `getUserLibraryArtistAlbums()` functions

### How It Works Now
User Library hierarchy matches Master Library:
1. **Artists view**: Shows artists where you have hearted content
2. **Click artist**: Shows that artist's albums in your library
3. **Click album**: Opens AlbumModal with tracks

No more flat "Tracks" view. The hierarchy is always Artist -> Album -> Tracks.

### Cache Invalidation
Updated all heart handlers to invalidate new query keys:
- `user-library-artists`
- `user-library-artist-albums`

---

## [0.1.107] - 2026-01-26

### TL;DR
- Fixed User Library Tracks view to show ALL tracks from hearted albums

### Fixed
- **user_library.py**: `get_library_tracks()` now returns tracks from hearted albums, not just individually hearted tracks
- **user_library.py**: `get_hearted_track_ids()` includes tracks from hearted albums for consistent is_hearted state
- **user_library.py**: `is_track_hearted()` checks both individual track hearts AND album-level hearts

### Root Cause
When user hearts an ALBUM, only the album was added to user_albums table. The tracks from that album did NOT appear in User Library Tracks view because `get_library_tracks()` only queried user_tracks table (individually hearted tracks).

Now the query uses UNION to include BOTH:
1. Individually hearted tracks (user_tracks)
2. All tracks from hearted albums (user_albums)

---

## [0.1.106] - 2026-01-26

### TL;DR
- Fixed heart state not syncing between Master Library and User Library

### Fixed
- **AlbumCard.jsx**: Added full cache invalidation (artists, artist-albums, albums, search-local)
- **ArtistCard.jsx**: Added full cache invalidation (artists, artist-albums, albums, search-local)
- **AlbumModal.jsx**: Added missing user-library-tracks + full cache invalidation
- **TrackRow.jsx**: Added full cache invalidation (artists, artist-albums, albums, search-local)
- **websocket.js**: Unified cache invalidation for download:complete, import:complete, library:updated events

### Root Cause
When hearting items, only user-library queries were invalidated. Missing invalidations:
- Master Library queries (artists, artist-albums, albums)
- Search results query (search-local)

This caused is_hearted to show stale cached data when navigating between pages.

---

## [0.1.105] - 2026-01-26

### TL;DR
- Login error now displays when wrong password entered

### Fixed
- **api.js**: 401 interceptor no longer redirects when already on login page, allowing error message to display

---

## [0.1.104] - 2026-01-26

### TL;DR
- Fixed track row button sizes - now properly sized per Braun design specs

### Fixed
- **TrackRow.jsx**: Icons increased from 24px to 32px (Braun xl size)
- **design-system.css**: Track buttons increased from 44px to 48px (Braun recommended touch target)
- **design-system.css**: Row height increased from 52px to 56px to accommodate larger buttons
- HeartIcon now uses dynamic stroke width (2.5px for 32px icons per Braun spec)

---

## [0.1.103] - 2026-01-26

### TL;DR
- Fixed hearted tracks not appearing in User Library

### Fixed
- **UserLibrary.jsx**: Tracks query now always fetches (was only fetching when tracks tab active)
- **TrackRow.jsx**: Added useEffect to sync local heart state from props (React state sync bug)
- **AlbumCard.jsx**: Added useEffect to sync local heart state from props
- **ArtistCard.jsx**: Added useEffect to sync local heart state from props
- **AlbumModal.jsx**: Added useEffect to sync local heart state from refetched data

### Technical
- Root cause 1: Tracks query had `enabled: viewMode === 'tracks'` so count showed 0 until clicked
- Root cause 2: useState only initializes on first render - if props change later, local state was stale
- All card/row components now sync their isHearted state when the prop changes via useEffect

---

## [0.1.102] - 2026-01-26

### TL;DR
- Fixed heart functionality not updating UI instantly across all views

### Fixed
- **AlbumModal.jsx**: TrackRow now receives `onHeart` callback - hearts in album view now trigger proper refresh
- **TrackRow.jsx**: Now invalidates album-specific queries when track is hearted (fixes stale heart state in album views)
- **AlbumCard.jsx**: Now invalidates `user-library-tracks` cache when album is hearted
- **ArtistCard.jsx**: Now invalidates `user-library-tracks` cache when artist is hearted

### Technical
- Root cause: Cache invalidation was incomplete across components
- Hearting a track in AlbumModal didn't trigger refetch because onHeart callback was missing
- Hearting albums/artists only invalidated album cache, not tracks cache
- All components now invalidate both `user-library` and `user-library-tracks` caches

---

## [0.1.101] - 2026-01-26

### TL;DR
- User Library now shows hearted tracks (not just albums)

### Added
- **user_library.py**: `get_library_tracks()` method to fetch hearted tracks with album/artist info
- **library.py**: `GET /me/library/tracks` endpoint to return user's hearted tracks
- **api.js**: `getUserLibraryTracks()` function
- **UserLibrary.jsx**: Albums/Tracks toggle - view either hearted albums or hearted tracks
- **design-system.css**: `.view-toggle` styles for album/track switcher

### Fixed
- **TrackRow.jsx**: Now displays album info correctly with flat field format (`album_title`, `artist_name`)
- **TrackRow.jsx**: Now invalidates `user-library-tracks` cache on heart/unheart
- **websocket.js**: Now invalidates `user-library-tracks` cache on library updates and download complete

### Technical
- Hearted tracks were being saved to DB but never displayed anywhere
- Users can now independently heart: artists (all albums), albums, or individual tracks
- All three appear in My Library with the new toggle

---

## [0.1.100] - 2026-01-26

### TL;DR
- Fixed Plex not recognizing user library symlinks

### Fixed
- **symlink.py**: Now creates relative symlinks instead of absolute paths (fixes Plex cross-mount issues)

### Added
- **CLI**: `barbossa library rebuild-symlinks` - regenerates all symlinks from database
  - Use when symlinks are missing or corrupted
- **CLI**: `barbossa library fix-symlinks` - converts absolute symlinks to relative
  - Use to fix existing symlinks without recreating

### Technical
- Absolute symlinks like `/music/artists/...` fail when Plex mounts the volume at a different path
- Relative symlinks like `../../../../artists/...` work regardless of mount point
- The rebuild-symlinks command deletes and recreates all symlinks based on hearted albums in database

---

## [0.1.99] - 2026-01-26

### TL;DR
- Master Library now updates instantly when album import completes

### Fixed
- **websocket.js**: `import:complete` handler now invalidates library queries (was only showing notification)
- **websocket.js**: Fixed field names in notification (`artist_name`/`album_title` instead of `artist`/`album`)

---

## [0.1.98] - 2026-01-26

### TL;DR
- Fixed heart functionality: cache invalidation, cross-page sync, added album heart in modal

### Fixed
- **ArtistCard.jsx**: Heart now invalidates react-query cache so My Library updates immediately
- **AlbumCard.jsx**: Heart now invalidates react-query cache so My Library updates immediately
- **TrackRow.jsx**: Heart now invalidates react-query cache so My Library updates immediately
- **AlbumModal.jsx**: Added album-level heart button (previously only tracks had hearts)

### Added
- **design-system.css**: New `.heart-btn-lg` style for album modal heart button
- All card components now support `onHeart` callback for parent notification

### Technical
- When hearting/unhearting from Master Library, My Library page now updates without refresh
- AlbumModal now shows album heart button alongside Play All button

---

## [0.1.97] - 2026-01-26

### TL;DR
- Fixed console errors: missing fonts, 403 on admin endpoints, missing favicon

### Fixed
- **design-system.css**: Commented out broken @font-face rules for Braun Linear fonts (font files don't exist, CSS gracefully falls back to system fonts)
- **Settings.jsx**: Admin API calls (getUsers, getPendingReview) now conditional on user.is_admin
- **Settings.jsx**: Users/Review tabs only shown to admin users
- **index.html**: Added favicon using existing placeholder-album.svg

### Technical
- Fonts: The CSS already had system font fallbacks; removed 404 errors by commenting out missing @font-face src urls
- 403 errors: Settings page was calling admin-only endpoints regardless of user role
- NotFoundError (bootstrap-autofill-overlay.js): Browser extension issue, not fixable on our end

---

## [0.1.96] - 2026-01-26

### TL;DR
- Added debug logging to Player for stream auth troubleshooting

### Changed
- **Player.jsx**: Added console logs to debug token availability and stream URL

---

## [0.1.95] - 2026-01-26

### TL;DR
- Fixed audio streaming 401 error - audio now plays correctly

### Fixed
- **dependencies.py**: Added get_stream_user dependency that accepts token from query param
- **streaming.py**: Stream endpoint now uses get_stream_user for audio element compatibility
- **Player.jsx**: Passes auth token as query parameter to stream URL
- **TrackRow.jsx**: Removed debug console.log statements

### Technical
- Audio elements cannot send Authorization headers, so token must be passed as query param
- Backend now accepts both header and query param authentication for streaming

---

## [0.1.94] - 2026-01-26

### TL;DR
- Play button always visible, shows pause icon when track is playing

### Changed
- **TrackRow.jsx**: Play button always visible, toggles to pause when playing
- **TrackRow.jsx**: Added PauseIcon component
- **TrackRow.jsx**: Uses player store to check current track state
- **design-system.css**: Removed opacity: 0 from track-play

---

## [0.1.93] - 2026-01-26

### TL;DR
- Braun-compliant track row buttons: 44px touch targets, 24px icons

### Changed
- **TrackRow.jsx**: Removed btn-icon class, icons now 24px each
- **design-system.css**: Track buttons now 44px touch targets per Braun spec

---

## [0.1.92] - 2026-01-26

### TL;DR
- Fixed track row heart (24px) and play button (20px) sizing and padding

### Changed
- **TrackRow.jsx**: Heart icon 24px, play icon 20px
- **design-system.css**: Fixed btn-icon padding override, proper sizing for track buttons

---

## [0.1.91] - 2026-01-26

### TL;DR
- Album modal UI improvements: larger hearts, play buttons, hover-only edit icon

### Changed
- **TrackRow.jsx**: Heart icon size increased from 16px to 20px
- **TrackRow.jsx**: Added play button between heart and track number (visible on hover)
- **AlbumModal.jsx**: Edit artwork icon now only shows on hover
- **AlbumCard.jsx**: Removed source badge (Qobuz pill) from album cards
- **design-system.css**: Added .track-play styles for new play button

---

## [0.1.90] - 2026-01-26

### TL;DR
- Swapped edit and delete button positions on album/artist cards

### Changed
- **AlbumCard.jsx**: Delete button now top-left, Edit button now top-right
- **ArtistCard.jsx**: Delete button now top-left, Edit button now top-right

---

## [0.1.89] - 2026-01-26

### TL;DR
- Clicking artwork navigates to album page; only pencil icon edits artwork

### Changed
- **ArtistCard.jsx**: Removed click-on-artwork edit behavior (navigates to albums instead)
- **AlbumCard.jsx**: Removed click-on-artwork edit behavior (opens modal instead)
- **techguide.md**: Added artist artwork endpoints documentation

---

## [0.1.88] - 2026-01-26

### TL;DR
- Added API endpoints to fetch missing artist artwork from Qobuz

### Added
- **artwork.py**: POST /api/artists/{id}/artwork/fetch - fetch single artist image from Qobuz
- **artwork.py**: POST /api/artwork/artists/fetch-all - batch fetch all missing artist images

### Tested
- Fetched artwork for Nine Inch Nails (1920x1283) and Post Malone (1080x1080)
- John & Mary and Honestav not found on Qobuz (expected - less popular artists)

---

## [0.1.87] - 2026-01-26

### TL;DR
- Edit artwork UI added to artist cards, album cards, and album modal

### Added
- **ArtistCard.jsx**: Pencil icon (top-left) on hover to edit artwork, click artwork opens file picker
- **AlbumCard.jsx**: Pencil icon (top-left) on hover to edit artwork, click artwork opens file picker
- **AlbumModal.jsx**: Edit artwork button (bottom-right of artwork), click artwork opens file picker
- **design-system.css**: .edit-btn styling

---

## [0.1.86] - 2026-01-26

### TL;DR
- Trash icon moved to top-right (was top-left)
- Artist artwork upload endpoint added
- Qobuz artist images now download during album import

### Added
- **artwork.py**: PUT /api/artists/{artist_id}/artwork endpoint for custom artist thumbnails
- **artwork.py**: DELETE /api/artists/{artist_id}/artwork to restore original
- **import_service.py**: fetch_artist_image_from_qobuz() downloads artist images from Qobuz API
- **download.py**: Automatically fetches artist image when importing Qobuz albums
- **api.js**: uploadArtistArtwork() and restoreArtistArtwork() frontend functions
- **design-system.css**: .album-action-top-right positioning class

### Changed
- **ArtistCard.jsx**: Trash icon now positioned top-right (was top-left)
- **AlbumCard.jsx**: Trash icon now positioned top-right (was top-left)
- **contracts.md**: Updated trash icon position specification to top-right

---

## [0.1.85] - 2026-01-26

### TL;DR
- Artist thumbnails now display using first album's cover art as fallback

### Added
- **streaming.py**: GET /api/artists/{artist_id}/artwork endpoint
  - Returns artist's own artwork if available
  - Falls back to first album's cover art
  - Searches common artwork filenames (cover.jpg, folder.jpg, etc.)
- **test_artist_artwork.py**: 10 comprehensive tests for artist artwork and heart endpoints

### Fixed
- **ArtistCard.jsx**: Always tries to load artwork from endpoint, shows initial only on error
  - Previously only tried if artwork_path was set (which was never populated)
  - Now uses onError fallback to show initial letter placeholder

### Test Coverage
- 188 tests total (all passing)
- New tests cover: artwork endpoint, heart/unheart endpoints, is_hearted field

---

## [0.1.84] - 2026-01-26

### TL;DR
- Added heart icon to artist cards for adding/removing artists from user library

### Added
- **ArtistCard.jsx**: Heart icon (bottom-left) to add/remove all artist albums from library
- **api.js**: heartArtist and unheartArtist API functions
- **library.py (API)**: POST/DELETE /me/library/artists/{artist_id} endpoints
- **user_library.py (service)**: heart_artist, unheart_artist, is_artist_hearted, get_hearted_artist_ids methods
- **artist.py (schema)**: is_hearted field added to ArtistResponse

### Behavior
- Heart on artist card adds ALL albums by that artist to user library
- Unheart removes ALL albums by that artist from user library
- Artist list_artists, get_artist, and search endpoints now return is_hearted status
- Artist cards now match album cards with same hover actions (heart, trash)

---

## [0.1.83] - 2026-01-26

### TL;DR
- Restored artist delete functionality on Master Library with mouse hover

### Fixed
- **ArtistCard.jsx**: Added trash icon that appears on 1-second hover (was missing)
- **ArtistGrid.jsx**: Added onArtistDelete prop passthrough
- **Library.jsx**: Added refetchArtists after artist deletion
- **api.js**: Added deleteArtist API function
- **library.py (API)**: Added DELETE /artists/{id} endpoint
- **library.py (service)**: Added delete_artist method to LibraryService

### Behavior
- Hover over artist card for 1 second, trash icon appears at top-left
- Click trash to delete artist and all their albums from disk
- Confirmation dialog warns user before deletion

---

## [0.1.82] - 2026-01-26

### TL;DR
- Fixed tracks not showing in album modal - staleTime was preventing refetch

### Fixed
- **AlbumModal.jsx**: Added staleTime: 0 to force refetch of album details with tracks
- Global staleTime of 5 minutes was caching album data without tracks

---

## [0.1.81] - 2026-01-26

### TL;DR
- Library pages now show Artists first, then Albums, then Tracks (per original spec)
- Both Master Library and User Library now have identical navigation flow

### Fixed
- **Library.jsx**: Now shows Artists grid first, click artist to see their albums, click album for tracks
- **UserLibrary.jsx**: Now shows Artists grouped from hearted albums, same navigation flow
- Added ArtistCard.jsx and ArtistGrid.jsx components
- Added back button and page header styling for drill-down navigation
- A-Z filter now filters Artists (not Albums)

### Behavior Change
- Navigation: Artists -> Albums -> Tracks (was: Albums -> Tracks)
- Master Library and User Library now feel identical per contracts.md

---

## [0.1.80] - 2026-01-26

### TL;DR
- Library now auto-refreshes when downloads complete - no more manual refresh needed

### Fixed
- **downloads.py tasks**: Now broadcasts download:complete and library:updated via WebSocket
- **websocket.js**: Invalidates react-query cache on library updates to auto-refresh UI
- **queryClient.js**: New shared QueryClient instance for cache invalidation from WebSocket
- **index.jsx**: Uses shared queryClient instead of creating inline

### Behavior Change
- When a download finishes, library pages automatically refresh to show new album
- No more need to manually refresh browser to see downloaded music

---

## [0.1.79] - 2026-01-26

### TL;DR
- Fixed album artwork not displaying - removed auth requirement from artwork endpoint

### Fixed
- **streaming.py**: Artwork endpoint no longer requires authentication (img tags dont send auth headers)
- Album thumbnails will now display correctly in the library grid

---

## [0.1.78] - 2026-01-26

### TL;DR
- Added missing test assertion for album detail tracks response

### Fixed
- **test_library.py**: test_get_album now verifies tracks are returned in album detail response
- Validates tracks list contains 3 items with correct track_number and title
- Validates artist_name field is populated

### Test Coverage
- All 14 metadata-fix-popo.md issues now have code fixes AND test coverage

---

## [0.1.77] - 2026-01-26

### TL;DR
- P3 fixes: WebSocket download progress now works, quality display handles None values
- Real-time download updates will now broadcast to connected users

### Fixed
- **downloads.py tasks**: Fixed WebSocket broadcast - was importing non-existent `broadcast_progress`, now uses correct `broadcast_download_progress` with user_id
- **downloads.py tasks**: Both Qobuz and URL download tasks now broadcast progress to the correct user
- **track.py model**: quality_display now handles None bitrate (defaults to 256 for lossy, shows format only if no quality data)

### Impact
- Issue 5 (Download Tracking): FIXED - WebSocket broadcasts progress to user
- Issue 12 (Quality Display): FIXED - no more "Nonekbps" display

---

## [0.1.76] - 2026-01-26

### TL;DR
- P1 fixes: Track responses now include artist/album context for player, delete refreshes UI
- Player will now show artist name and album artwork during playback

### Fixed
- **track.py schema**: Added artist_name, album_title, artwork_path fields for player display
- **track.py schema**: from_orm_with_quality now populates album/artist context
- **library.py service**: Eager loads album.artist for track queries (get_album_tracks, search)
- **AlbumCard.jsx**: Now calls onDelete callback after successful delete
- **AlbumGrid.jsx**: Passes onAlbumDelete prop to AlbumCard
- **Library.jsx**: Passes onAlbumDelete that triggers refetch
- **UserLibrary.jsx**: Passes onAlbumDelete that triggers refetch

### Impact
- Issue 6 (Delete Refresh): FIXED - UI updates immediately after delete
- Issue 9 (Track Artist): FIXED - player has artist/album context

---

## [0.1.75] - 2026-01-26

### TL;DR
- P0 fixes: Artist now shows correctly, albums now return tracks, play function works
- ExifTool now reads ALBUMARTIST (Qobuz primary tag), DATE/ORIGINALDATE for year, DiscNumber
- Album detail API now includes tracks list - frontend play function will work
- All album lists now include artist_name field

### Fixed
- **exiftool.py**: Artist extraction now prefers ALBUMARTIST over Artist (Qobuz uses ALBUMARTIST)
- **exiftool.py**: Year extraction now falls back to DATE and ORIGINALDATE tags
- **exiftool.py**: Added DiscNumber and Genre extraction
- **album.py schema**: Added artist_name to AlbumResponse, tracks list to AlbumDetailResponse
- **library.py API**: Album detail now returns full track list with all metadata
- **library.py API**: All album endpoints now return artist_name
- **library.py service**: Added eager loading for artist relationship in list_albums and search
- **user_library.py**: Added eager loading for artist relationship in get_library
- **import_service.py**: Disc number now uses metadata instead of hardcoded 1
- **import_service.py**: Artwork extraction now tries embedded FLAC art during import (not just after beets fails)

### Impact
- Issue 1 (Thumbnails Missing): FIXED - embedded artwork extracted during import
- Issue 2 (Artist Unknown): FIXED
- Issue 3 (No Tracks): FIXED
- Issue 4 (Play Broken): FIXED (depends on Issue 3)
- Issue 7 (User Library Artist): FIXED
- Issue 8 (Album Schema): FIXED
- Issue 10 (Year/Genre): FIXED
- Issue 11 (Disc Number): FIXED

---

## [0.1.74] - 2026-01-26

### TL;DR
- Full metadata audit: 12 critical issues identified in Qobuz download pipeline
- Root causes found for missing thumbnails, unknown artists, no track lists, broken play

### Added
- docs/metadata-fix-popo.md - Complete audit report with fix plan

### Audit Findings
1. **Thumbnails missing** - _find_artwork() doesn't extract embedded art from FLAC files
2. **Artist always "Unknown"** - ExifTool reads "Artist" but Qobuz uses "ALBUMARTIST"
3. **No track list** - AlbumDetailResponse schema has no tracks field, API doesn't return them
4. **Play broken** - Depends on issue 3 (no tracks = can't play)
5. **Download tracking** - Data IS in database (Download model), WebSocket broken due to import mismatch (broadcast_progress vs broadcast_download_progress)
6. **Delete no refresh** - Parent component doesn't refresh after card-level delete
7. **User library artist** - get_library() doesn't eager load artist relationship
8. **Album schema** - AlbumResponse missing artist_name field
9. **Track schema** - TrackResponse missing artist context for player display
10. **Year/Genre** - ExifTool may need DATE/ORIGINALDATE fallbacks
11. **Disc number** - Hardcoded to 1, ignores metadata
12. **Quality display** - None values cause "Nonekbps" display

### Fix Priority
- P0: Issues 2, 3 (blocks entire UX)
- P1: Issues 1, 8, 9, 6
- P2: Issues 7, 11, 10
- P3: Issues 5, 12

---

## [0.1.73] - 2026-01-26

### TL;DR
- Fixed beets CLI command syntax and album name parsing
- Downloads should now complete successfully through the full pipeline

### Fixed
- **beets.py**: Fixed CLI syntax - `-c` config flag now placed BEFORE subcommand
- **beets.py**: Album name parsing now uses `_parse_folder_name()` to extract just album title from streamrip folder format (was using full folder name including artist)

### Technical
- Streamrip folders are named `Artist - Album (Year) [Format]`
- Previously passed full name to `_find_imported_path()` causing "Could not find imported album: Artist - Artist - Album" errors

---

## [0.1.72] - 2026-01-26

### TL;DR
- Fixed download pipeline - downloads now actually work end-to-end
- Fixed beets output parsing, streamrip folder detection, disabled download tracking

### Fixed
- **beets.py**: Parser no longer treats error messages as artist names (skip "No files imported" lines)
- **streamrip.py**: Disabled downloads.db tracking to allow re-downloads
- **streamrip.py**: Folder detection now finds existing folders with audio files instead of erroring

### Root Causes Found
1. Streamrip marked tracks as "already downloaded" blocking re-downloads
2. Folder detection failed when no NEW folder created (existing album)
3. Beets error output parsed as metadata causing garbage artist names
4. SMB mount issues causing .smbdelete file artifacts

---

## [0.1.71] - 2026-01-26

### TL;DR
- Fixed all Pydantic V2 and datetime deprecation warnings
- Updated FastAPI to use lifespan context manager

### Fixed
- Replaced deprecated `class Config` with `model_config = ConfigDict(...)` in all Pydantic schemas
- Replaced deprecated `datetime.utcnow()` with `datetime.now(timezone.utc)` throughout codebase
- Replaced deprecated `@app.on_event("startup")` with lifespan context manager in main.py

---

## [0.1.70] - 2026-01-26

### TL;DR
- Added full E2E test infrastructure with real audio fixtures
- Added comprehensive admin auth integration tests for review API
- All 36 CLI import + review API tests passing

### Added
- **conftest.py**: `real_audio_sample` fixture - generates valid WAV audio bytes
- **conftest.py**: `audio_album_folder` fixture - creates test album with real audio
- **conftest.py**: `mock_beets_client` / `mock_exiftool_client` factory fixtures
- **conftest.py**: `pending_review_with_files` fixture - review with actual audio on disk
- **test_cli_import_e2e.py**: `TestCLIImportWithRealAudio` - 4 tests with real audio validation
- **test_cli_import_e2e.py**: `TestCLIImportErrorRecovery` - 2 error handling tests
- **test_review_api_e2e.py**: `TestReviewIntegrationWithRealAudio` - 4 full pipeline tests
- **test_review_api_e2e.py**: `TestAdminAuthenticationEnforcement` - 3 auth verification tests
- **test_review_api_e2e.py**: `TestReviewApprovalErrorHandling` - 3 error handling tests

### Fixed
- Tests now properly verify admin-only endpoints reject regular users
- Tests verify artwork fetch is called when artwork_path is None
- Tests verify artwork fetch is skipped when artwork already exists

---

## [0.1.69] - 2026-01-26

### TL;DR
- Fixed all e2e tests: 20 CLI import + review API tests now passing
- Fixed FastAPI route ordering bug in /failed endpoint
- Total: 162 tests passing

### Fixed
- **Review API route order**: Moved /failed endpoint before /{review_id} to prevent "failed" being captured as review_id
- **CLI e2e tests**: Fixed typer runner import and invocation pattern (admin prefix)
- **CLI e2e tests**: Fixed mock patch locations for imports inside function scope

### Added
- tests/test_cli_import_e2e.py - 7 comprehensive CLI import tests with mocks
- tests/test_review_api_e2e.py - 13 review API flow tests (approve, reject, failed, 404s)

---

## [0.1.68] - 2026-01-26

### TL;DR
- Implemented all P0/P1 remediation fixes: safe deletion, CLI artwork, import rollback, review failure handling
- Added 13 new tests, all 142 tests passing

### Fixed
- **P0 File Deletion**: delete_album() now returns (success, error) tuple; deletes files FIRST before DB record; returns False with error message if file deletion fails, preserving DB record for retry
- **P1 CLI Artwork**: CLI import now calls fetch_artwork_if_missing() after successful import
- **P1 Import Rollback**: _import_album() in download.py now has try/except that moves files to /import/failed/ on DB error instead of leaving orphans
- **P1 Review Retry Bug**: process_review task marks review as "failed" (not "pending") on error, preventing retry loops with already-moved files

### Added
- PendingReviewStatus.FAILED status for failed review imports
- GET /api/import/review/failed endpoint to list failed reviews
- tests/test_deletion.py - 8 tests for delete_album return values and API
- tests/test_review_flow.py - 2 tests for review status handling
- tests/test_import_rollback.py - 3 tests verifying rollback code structure

### Changed
- LibraryService.delete_album() signature: now returns tuple[bool, str|None] instead of bool
- DELETE /api/albums/{id} now accepts delete_files query param and returns proper 500 on file errors

---

## [0.1.67] - 2026-01-26

### TL;DR
- Added admin role enforcement, import pipeline fixes, beets config provisioning, artwork recovery, duplicate download status, safer export/backup paths, review reject handling, and test reliability fixes.

### Added
- Admin role flag on users with admin-only guards for admin and review endpoints
- Duplicate download status handling with UI messaging
- Beets config provisioning at startup when missing

### Fixed
- Auth now returns 401 for missing credentials
- Import task await bug and watcher scheduling on the main event loop
- Review records now capture source and basic quality info
- Review rejects move albums into the rejected folder when not deleting
- Artist sort names are now populated for stable ordering
- Replace-album refreshes import history and checksums
- Beets API path now loads config when present, else falls back to CLI
- Artwork recovery after download/import approvals
- Deleting albums now removes user library links
- Export and backup destinations constrained to configured roots
- Qobuz tests skip when host is not reachable
- Alembic 006 migration now safely skips drop if is_admin is missing
- Beets import now falls back to locating album by track filename when path lookup fails
- Delete now removes SMB .smbdelete* files before rmtree

## [0.1.62] - 2026-01-25

### Fixed - CLI and GUI Import Flow

**CLI typer compatibility fix**
- Upgraded typer from 0.9.0 to 0.21.1 (click 8.3.x compatibility)
- Fixed TyperArgument.make_metavar() signature mismatch
- CLI import now correctly handles multi-word arguments (e.g., --artist "Nine Inch Nails")

**GUI import approve flow fix**
- Changed approve endpoint to use import_with_metadata() instead of import_album()
- More reliable file handling without depending on beets auto-detection
- Now properly respects artist/album/year overrides from user

**SMB temp file cleanup**
- Cleaned up .smbdelete* temp files left by SMB mount operations
- Removed empty directories in library structure

### Files Modified
- backend/requirements.txt - typer 0.9.0 -> 0.21.1
- backend/app/api/review.py - Use import_with_metadata for approve

---

## [0.1.61] - 2026-01-25

### Fixed - Critical Audit Issues

**P0 - Album deletion now removes files from disk**
- delete_album() now deletes files via shutil.rmtree() (was DB-only)
- Cleans up empty artist directories after deletion
- Optional delete_files=False parameter to preserve files if needed

**P1 - CLI import command added**
- `barbossa admin import <path>` imports albums from folder
- Supports --artist, --album, --year overrides
- Duplicate detection with --force override
- Shows artwork status after import

**P1 - Library rescan implemented**
- `barbossa admin rescan` scans library and indexes new albums
- Supports --path for specific directory
- Supports --dry-run to preview without changes
- Reports existing vs new album counts

**P2 - Artwork fetch after import**
- New fetch_artwork_if_missing() method in ImportService
- Tries beets fetchart, Cover Art Archive, embedded extraction
- Import task now fetches artwork if beets didn't get it

**P3 - Beets integration rewritten**
- Now uses beets Python API when available (more reliable)
- Falls back to CLI parsing when API unavailable
- Direct MusicBrainz lookups via beets.autotag.mb
- File tagging via mediafile library
- Cover Art Archive direct fetch as fallback

### Added
- backend/tests/test_import_integration.py - Integration tests for import pipeline

### Files Modified
- backend/app/services/library.py - P0: File deletion on album delete
- backend/app/services/import_service.py - P2: Artwork fetch methods
- backend/app/integrations/beets.py - P3: Python API integration
- backend/app/tasks/imports.py - P2: Artwork fetch after import
- backend/app/cli/admin.py - P1: import and rescan commands

---

## [0.1.60] - 2026-01-25

### Removed - Dead Code Cleanup
- Removed unused `_import_trusted_source` method from download.py
- Method was never called - Qobuz downloads always use beets via `_import_album`

---

## [0.1.59] - 2026-01-25

### Fixed - SMB Folder Detection
- Streamrip now correctly identifies downloaded folders on SMB mounts
- Replaced unreliable mtime-based detection with before/after folder comparison
- Fixes issue where wrong album was processed after download

---

## [0.1.58] - 2026-01-25

### Changed - Qobuz Import Pipeline
- Qobuz downloads skip confidence threshold (min_confidence=0.0) so never go to review queue
- Beets still runs for metadata, artwork, and lyrics
- Added missing await for async import_service methods
- Added missing columns to tracks table (lyrics, musicbrainz_id, updated_at)

---

## [0.1.57] - 2026-01-25

### Fixed - Download Pipeline Robustness
- Streamrip downloads now succeed despite cleanup crashes on SMB mounts
- Added audio file validation to detect successful downloads regardless of exit code
- WebSocket broadcast_to_admins fixed (method didn't exist)
- Added fallback folder name parsing when beets can't identify album
- PendingReview model now includes source_url field

### Added
- Migration 009: source_url column for pending_review table

---

## [0.1.56] - 2026-01-25

### Fixed - Streamrip Download Command
- Removed invalid --quality and --output flags from rip url command
- Streamrip config now syncs download folder to /music/downloads/qobuz
- Config persists via barbossa_streamrip Docker volume

---

## [0.1.55] - 2026-01-25

### Fixed - Downloads Queue
- Queue endpoint now includes pending_review status (downloads no longer disappear after review)
- Fixed cancel button: was calling DELETE (for deleting records) instead of POST /cancel (for cancelling active downloads)

---

## [0.1.54] - 2026-01-25

### Added - Review Safety Net
- Low confidence beets matches (<85%) now go to review queue instead of failing
- Added PENDING_REVIEW status to download states
- Downloads page shows pending_review items with "Needs manual review" indicator
- Migration 008 adds result_review_id foreign key to downloads table

---

## [0.1.53] - 2026-01-25

### Changed - UX Improvements
- Default landing page changed from Master Library to My Library
- Removed redundant app header (page title already visible in sidebar)
- Master Library now at /master-library route
- Sidebar nav reordered: My Library first

---

## [0.1.52] - 2026-01-25

### Changed - Search Auto-Cascade
- Search now auto-cascades: Local -> Qobuz (automatic) -> Fallback modal
- Qobuz search triggers automatically when local results empty (no manual click needed)
- "Search more" button appears at bottom of local/Qobuz results for external sources
- Loading feedback shows search progress ("No results in library" -> "Searching Qobuz...")
- Fallback modal includes Qobuz option when user has local results (quality upgrade path)
- Qobuz results display alongside local results when triggered from modal (quality upgrade)
- Removed dead state variables (showExternal, externalSource, handleSearchExternal)
- Qobuz errors now auto-show fallback options with retry button

---

## [0.1.51] - 2026-01-25

### Fixed - Database Migration Chain
- Fixed alembic migration chain (006 down_revision pointed to wrong revision id)
- Added migration 007 for missing celery_task_id column in downloads table
- All migrations now run cleanly from scratch

### Verified - Qobuz API Live Testing
Live API endpoint testing completed:
- GET /api/qobuz/search - Returns albums with artwork URLs, quality badges
- GET /api/qobuz/artist/{id} - Returns full discography (tested: Pink Floyd 138 albums)
- GET /api/qobuz/album/{id} - Returns track listing with hi-res indicators
- Authentication required on all endpoints (JWT)
- Response includes in_library flag for local albums

---

## [0.1.50] - 2026-01-25

### Completed - Qobuz API Integration (Phase 8 - Testing and Polish)
Full Qobuz catalog browsing feature complete and tested.

### Test Coverage
- 27 Qobuz-specific tests (12 API client + 15 routes)
- 112 total backend tests passing
- All error handling verified

### Phase 8 Verification Checklist
- [x] Search artist returns results with images
- [x] Artist discography shows all albums with artwork and quality badges
- [x] Album page shows track listing with quality indicators
- [x] Multi-disc albums display with disc section headers
- [x] Download button starts download and shows notification
- [x] "In Library" badges show on already-downloaded albums
- [x] Error states display with Retry button
- [x] API errors return proper 502 status
- [x] Invalid credentials show appropriate error message
- [x] Lazy loading enabled for images
- [x] Response caching (5 min TTL) reduces API calls
- [x] Rate limiting (50 req/min) prevents blocks

### Files Verified
- backend/app/integrations/qobuz_api.py - API client with auth, caching, rate limiting
- backend/app/api/qobuz.py - REST endpoints with in_library detection
- backend/tests/test_qobuz_api.py - 12 API client tests
- backend/tests/test_qobuz_routes.py - 15 route tests
- frontend/src/pages/Search.jsx - Qobuz search with artwork grid
- frontend/src/pages/QobuzArtist.jsx - Artist discography page
- frontend/src/pages/QobuzAlbum.jsx - Album detail page with tracks
- frontend/src/styles/qobuz.css - Dedicated stylesheet
- frontend/public/placeholder-album.svg - Fallback image
- frontend/public/placeholder-artist.svg - Fallback image

---

## [0.1.49] - 2026-01-25

### Added - Qobuz Styling (Phase 7)
- Dedicated qobuz.css stylesheet for all Qobuz catalog browsing components
- Uses Barbossa design system tokens (spacing, colors, typography, transitions)
- Full responsive design for mobile devices

### Styles Added
- Search results grid with hover effects
- Album cards with artwork, quality badges, and actions
- Artist cards in search results
- Track list items with artwork thumbnails
- Artist page header and discography grid
- Album page header and track listing table
- Multi-disc album support with disc section headers
- Breadcrumb navigation
- In-library badges
- Sort options dropdown
- Quality indicators (Hi-Res, CD)
- Button variants (btn-sm, btn-large)

### Files Created
- frontend/src/styles/qobuz.css

### Files Modified
- frontend/src/index.jsx - Import qobuz.css

---

## [0.1.48] - 2026-01-25

### Added - Qobuz Album Detail Page (Phase 6)
- QobuzAlbum.jsx - View album tracks before downloading
- Album header with large artwork, artist link, year, track count, total duration
- Quality badge showing Hi-Res (bit depth/sample rate) or CD quality
- Genre and label tags display
- Multi-disc album support with disc section headers
- Track listing table with track number, title, duration, quality indicator
- Download button (or "Already in Library" badge if downloaded)
- Breadcrumb navigation (Back / Artist / Album)
- Responsive design for mobile

### Files Created
- frontend/src/pages/QobuzAlbum.jsx

### Files Modified
- frontend/src/App.jsx - Added /qobuz/album/:albumId route
- frontend/src/styles/design-system.css - Album page styles (header, tracks table, disc sections)

---

## [0.1.47] - 2026-01-25

### Added - Qobuz Artist Discography Page (Phase 5)
- QobuzArtist.jsx - Browse artist's full catalog with artwork
- Artist header with large image and album count
- Discography grid with all albums showing artwork and quality badges
- Sort options (year/title)
- Quick download button per album
- "In Library" badges for albums already downloaded
- Biography section (if available from Qobuz)
- Breadcrumb navigation
- Responsive design for mobile

### Files Created
- frontend/src/pages/QobuzArtist.jsx

### Files Modified
- frontend/src/App.jsx - Added /qobuz/artist/:artistId route
- frontend/src/styles/design-system.css - Artist page styles (breadcrumbs, header, grid)

---

## [0.1.46] - 2026-01-25

### Fixed - Phase 4 Audit Items
- Added placeholder SVGs for missing album/artist images
- Added Qobuz search error state with Retry button
- Standardized image placeholders to use SVG fallbacks instead of text

### Files Created
- frontend/public/placeholder-album.svg - Vinyl record placeholder
- frontend/public/placeholder-artist.svg - Person silhouette placeholder

### Files Modified
- frontend/src/pages/Search.jsx - Error handling, standardized placeholders
- frontend/src/styles/design-system.css - Added .error-actions styling

---

## [0.1.45] - 2026-01-25

### Updated - Search Page Qobuz Display (Phase 4)
- Search page now uses searchQobuzCatalog endpoint (artwork URLs, in_library status)
- Album search results display in responsive grid with artwork
- Quality badges show hi-res bit depth/sample rate (e.g., 24/192)
- "In Library" badges on albums already downloaded
- Artist names link to /qobuz/artist/{id} discography page
- "View Tracks" button links to /qobuz/album/{id} detail page
- Artist search results display with images and album counts
- Track search results display with album artwork thumbnails

### Files Modified
- frontend/src/pages/Search.jsx - Updated Qobuz query and results display
- frontend/src/styles/design-system.css - Added Qobuz catalog CSS (grid, cards, badges)

---

## [0.1.44] - 2026-01-25

### Added - Qobuz Frontend API Service (Phase 3)
- searchQobuzCatalog() - Search Qobuz catalog with artwork URLs
- getQobuzArtist() - Get artist details with full discography, sort option
- getQobuzAlbum() - Get album details with track listing

### Files Modified
- frontend/src/services/api.js - Added 3 new Qobuz catalog browsing functions

---

## [0.1.43] - 2026-01-25

### Fixed - Qobuz Phase 2 Audit Items
- preview_url now constructs actual Qobuz streaming URL when track is previewable
- Library check filter now uses SQLAlchemy has() for cleaner relationship query
- Removed unused Artist model import from qobuz.py

### Files Modified
- backend/app/integrations/qobuz_api.py - preview_url now generates URL from previewable flag
- backend/app/api/qobuz.py - check_albums_in_library uses has() filter, removed unused import

### Test Status
- 27 Qobuz tests passing

---

## [0.1.42] - 2026-01-25

### Added - Qobuz API Routes (Phase 2)
- backend/app/api/qobuz.py - REST endpoints for Qobuz catalog browsing
- GET /api/qobuz/search - Search albums, artists, or tracks with artwork URLs
- GET /api/qobuz/artist/{id} - Artist details with full discography
- GET /api/qobuz/album/{id} - Album details with track listing
- All endpoints include `in_library` flag for albums already in local library
- Artist discography supports sorting by year (default) or title
- Normalized matching for library detection (ignores case, deluxe editions, etc.)
- backend/tests/test_qobuz_routes.py - 15 tests for Qobuz endpoints

### Files Created
- backend/app/api/qobuz.py
- backend/tests/test_qobuz_routes.py

### Files Modified
- backend/app/api/__init__.py - Added qobuz router

### Test Status
- 112 tests passing (97 existing + 15 new)

---

## [0.1.41] - 2026-01-25

### Fixed - Qobuz API Tests, Region Support, App Credentials
- Tests now skip when Qobuz not fully configured (credentials + app_id)
- Added `reset_qobuz_api()` function for test isolation
- Fixed singleton pattern to support multiple regions
- `get_qobuz_api(region="uk")` now creates region-specific instances
- Added configurable QOBUZ_APP_ID and QOBUZ_APP_SECRET env vars
- Auto-extracts app credentials from streamrip config if available
- Fixed .env loading to check parent directory (barbossa/.env)

### Files Modified
- backend/app/config.py - Added qobuz_app_id, qobuz_app_secret; env_file tuple
- backend/app/integrations/qobuz_api.py - Configurable app credentials, streamrip extraction
- backend/tests/test_qobuz_api.py - Skip markers check both user and app credentials

### Test Status
- 12 passed (all tests including integration tests)

### Qobuz Setup Completed
- Streamrip configured with valid app_id (798273057) and secrets
- Credentials stored in ~/Library/Application Support/streamrip/config.toml
- QobuzAPI auto-extracts app credentials from streamrip config

---

## [0.1.40] - 2026-01-25

### Added - Qobuz API Client (Phase 1)
- backend/app/integrations/qobuz_api.py - Direct Qobuz API client for catalog browsing
- Enables fetching album/artist artwork URLs (not available via streamrip CLI)
- Features: search albums/artists/tracks, get artist discography, get album track listing
- Includes rate limiting (50 req/min), response caching (5 min TTL)
- Uses existing Qobuz credentials from settings (qobuz_email, qobuz_password)
- Streamrip still handles actual downloads
- backend/tests/test_qobuz_api.py - Integration tests

---

## [0.1.39] - 2026-01-25

### Added - Qobuz API Implementation Guide
- docs/qobuz-api-implementation-guide.md - 8-phase guide for direct Qobuz API integration
- Enables browsing artist discographies with album artwork before downloading
- Covers: backend API client, routes, frontend pages (artist, album), styles
- Uses existing Qobuz credentials (no new API key needed)
- Streamrip still used for actual downloads (handles DRM)

### Audit Fixes Added to Guide
- Rate limiting (50 req/min to avoid Qobuz blocks)
- Response caching (5 min TTL for artist/album data)
- "Already in Library" badges on albums
- Multi-disc album handling with disc headers
- Sort options for artist discography (year/title)
- Breadcrumb navigation on artist/album pages
- Image error fallbacks with placeholder SVGs
- Genre and label display on album pages
- User authentication required on all endpoints
- httpx dependency documented

---

## [0.1.38] - 2026-01-25

### Fixed - Qobuz Search Not Working
Three bugs fixed:

1. **Wrong CLI syntax** - was using invalid `--type` and `--limit` flags
   - Fixed to: `rip search qobuz <type> <query> -n <limit> -o <file>`
   - Search now writes results to temp file and parses output properly

2. **Credentials not synced** - Barbossa settings were not being used by streamrip
   - Added `_sync_credentials()` method to StreamripClient
   - Automatically syncs Qobuz email/password from Barbossa settings to streamrip config
   - Password is MD5 hashed as required by streamrip
   - Credentials synced before each search/download operation

3. **Settings not persisting** - GUI settings only saved to memory, lost on restart
   - Added `_update_env_file()` function to persist settings to .env
   - All settings (Qobuz, Lidarr, Plex, paths) now persist across restarts

4. **JSON parser updated** - streamrip returns different JSON format than expected
   - Format: `[{"source": "qobuz", "id": "xxx", "desc": "Album by Artist"}]`
   - Parser now extracts artist/title from "desc" field

### Files Modified
- backend/app/integrations/streamrip.py - Fixed CLI syntax, credential sync, JSON parsing
- backend/app/api/settings.py - Added .env file persistence

---

## [0.1.37] - 2026-01-25

### Updated - Documentation for Search Redesign
- techguide.md: Added `/api/search/unified` endpoint documentation
- techguide.md: Added Sidebar.jsx, Header.jsx, Search.jsx component docs
- techguide.md: Added unified search parameters and response format
- Audit complete: All search redesign code matches plan

---

## [0.1.36] - 2026-01-25

### Added - Search Redesign Implementation
Implemented unified search system per docs/search-redesign-guide.md

**Backend:**
- backend/app/api/search.py: Unified search endpoint with Qobuz fallback
- backend/tests/test_search_unified.py: 12 tests for search endpoint
- Playlist type rejected per contracts.md line 94

**Frontend:**
- frontend/src/pages/Search.jsx: Dedicated search page with 6 UI states
- frontend/src/components/Sidebar.jsx: Search moved from header to sidebar
- frontend/src/components/Header.jsx: Simplified, shows page title only
- frontend/src/pages/Library.jsx: Removed search handling (browse only)
- frontend/src/pages/Downloads.jsx: Removed Qobuz search (keep URL paste + Lidarr)
- frontend/src/App.jsx: Added /search route
- frontend/src/services/api.js: Added searchUnified endpoint
- frontend/src/styles/design-system.css: Search page styles, dark mode support

**Search Flow:**
1. User searches in sidebar (type selector: Album/Artist/Track - NO Playlist)
2. Navigates to /search?q=X&type=Y
3. Local results displayed if found
4. If no local results: external options card (Qobuz, Lidarr, YouTube, URL paste)
5. Qobuz results with Download button
6. YouTube shows lossy warning

---

## [0.1.35] - 2026-01-25

### Added - Search Redesign Technical Guide
- docs/search-redesign-guide.md: Implementation guide for search overhaul (audited, rev 2)
- Addresses: Qobuz fallback, streamrip GUI gaps, sidebar search, unified search page
- Backend: Pydantic schemas, proper imports, test file
- Frontend: Search.jsx with 6 UI states, YouTube lossy warning
- CSS: Dark mode, mobile responsive, spinner

---

## [0.1.34] - 2026-01-25

### Added - Missing Subdirectories
Created required subdirectories per contracts.md specification:
- /Volumes/media/library/music/import/pending - Drop files here for import
- /Volumes/media/library/music/import/review - Beets unidentified content
- /Volumes/media/library/music/import/rejected - Duplicates/corrupt files
- /Volumes/media/library/music/downloads/qobuz - Streamrip output
- /Volumes/media/library/music/downloads/lidarr - Lidarr completed downloads
- /Volumes/media/library/music/downloads/youtube - yt-dlp output

### Verified
- All 73 backend tests passing
- All 5 directory paths correctly configured
- Frontend settings UI correctly translates container/host paths

---

## [0.1.33] - 2026-01-25

### Fixed - Path Configuration Audit
- Fixed .env MUSIC_PATH from /Volumes/media to /Volumes/media/library/music
- Fixed techguide.md diagram: changed "library/" to "artists/" to match contracts.md
- Added "database/" to techguide.md volume structure diagram

### Audit Results
All paths now correctly configured:
- /Volumes/media/library/music/artists - Master library (all music at artist level)
- /Volumes/media/library/music/users - Per-user symlinked libraries
- /Volumes/media/library/music/database - Database backups
- /Volumes/media/library/music/downloads - Temp download staging
- /Volumes/media/library/music/import - Watch folder for imports

### Files Modified
- .env - Corrected MUSIC_PATH and MUSIC_PATH_HOST
- techguide.md - Fixed volume structure diagram

---

## [0.1.32] - 2026-01-25

### Fixed - Admin System Cleanup
- Removed all remnants of admin user system that was already removed in 0.1.30
- Fixed bcrypt compatibility (pinned to 4.0.1 for passlib compatibility)
- Removed unused require_admin import from lidarr.py
- Fixed test assertions for unauthorized responses (401 vs 403)
- Fixed test fixtures calling create_user with removed is_admin parameter
- Fixed heart_workflow test to use "items" instead of "albums" in response
- Removed admin_connections from WebSocket manager
- Removed broadcast_to_admins calls from download progress broadcasts
- Removed admin-only checks from CLI auth commands
- Removed TestAdminWorkflow tests

### Files Modified
- backend/app/api/downloads.py - Removed is_admin checks, users see only their own downloads
- backend/app/api/exports.py - Removed is_admin checks, users see only their own exports
- backend/app/api/websocket.py - Removed is_admin parameter from manager.connect
- backend/app/api/lidarr.py - Removed unused require_admin import
- backend/app/websocket.py - Removed admin_connections, broadcast_to_admins method
- backend/app/cli/auth.py - Removed is_admin display in whoami and login
- backend/tests/test_auth.py - Fixed unauthorized test assertion (401)
- backend/tests/test_websocket.py - Removed admin_connections tests, fixed SessionLocal patches
- backend/tests/test_downloads.py - Removed admin_connections test
- backend/tests/test_e2e.py - Removed TestAdminWorkflow, fixed items vs albums in response

### Test Status
- All 73 tests passing

---

## [0.1.31] - 2026-01-25

### Changed - Path Configuration Standardized
- Master library path changed from /music/library to /music/artists
- All paths now consistent with user's directory structure:
  - /music/artists - Master library (all music at artist level)
  - /music/users - Per-user symlinked libraries
  - /music/database - Database backups
  - /music/downloads - Temp download staging
  - /music/import - Watch folder for imports
  - /music/export - Export destination

### Files Modified
- backend/app/config.py - Updated music_library default to /music/artists, added music_database
- backend/app/api/settings.py - Added music_database to SettingsResponse
- docker-compose.yml - Updated watch paths
- docker-compose.prod.yml - Changed MUSIC_LIBRARY env vars to /music/artists
- .env.example - Updated path documentation
- backups/backup.sh - Uses /music/database for backups
- contracts.md - Updated library structure diagram
- backend/tests/test_library.py - Updated test paths

### Documentation Updated
- techguide.md
- docs/phases/phase-1-core.md
- docs/cli-spec.md
- docs/playlist-sync.md
- docs/rclone-backup.md
- docs/bandcamp-integration.md
- docs/plex-integration.md
- docs/lidarr-integration.md
- docs/exiftool-integration.md
- docs/beets-integration.md

---

## [0.1.30] - 2026-01-25

### Removed - Admin User Concept
- Removed is_admin column from users table
- All authenticated users can now access all features
- Settings page accessible to all users
- Album deletion available to all users
- User management available to all users

### Files Modified
- backend/app/models/user.py - Removed is_admin column
- backend/app/schemas/user.py - Removed is_admin from schemas
- backend/app/services/auth.py - Removed is_admin parameter from create_user
- backend/app/dependencies.py - Removed require_admin function
- backend/app/api/auth.py - Removed is_admin from responses
- backend/app/api/admin.py - Replaced require_admin with get_current_user
- backend/app/api/settings.py - Replaced require_admin with get_current_user
- backend/app/api/review.py - Replaced require_admin with get_current_user
- backend/app/api/torrentleech.py - Replaced require_admin with get_current_user
- backend/app/api/library.py - Replaced require_admin with get_current_user
- backend/app/cli/admin.py - Removed admin-only checks
- backend/db/schema.sql - Removed is_admin column and default user
- backend/alembic/versions/001_initial_schema.py - Removed is_admin column
- backend/tests/conftest.py - Removed admin fixtures
- backend/tests/test_auth.py - Removed admin assertions
- frontend/src/App.jsx - Removed AdminRoute
- frontend/src/components/Sidebar.jsx - Settings link always visible
- frontend/src/components/AlbumCard.jsx - Trash icon available to all
- frontend/src/pages/Settings.jsx - Removed admin badges and checkbox
- frontend/src/services/websocket.js - Downloads channel for all users

### Files Created
- backend/alembic/versions/006_remove_admin_user.py - Migration to drop is_admin

---

## [0.1.29] - 2026-01-25

### Fixed - Qobuz Settings Not Persisting
- Qobuz credentials now properly save and persist across page refreshes
- Status pill (Connected/Not Configured) now updates immediately after saving
- Root cause: settings.py used stale module-level settings cache instead of fresh instance

### Files Modified
- backend/app/api/settings.py - Use get_settings() for fresh config after cache clear

---

## [0.1.28] - 2026-01-25

### Added - Qobuz Settings with Verification
- Qobuz email/password fields in Settings > Sources
- Individual Save buttons for each source (Qobuz, Lidarr, Plex)
- Visual verification of saved credentials:
  - Masked email display for Qobuz (e.g., "jo***@email.com")
  - Server URL display for Lidarr and Plex
  - "Connected" / "Not Configured" / "Disconnected" badges
- Clear labeling: "Update Email" vs "Email" based on saved state

### Files Modified
- frontend/src/pages/Settings.jsx - SourceSettings with saved credential display
- frontend/src/styles/design-system.css - .saved-credential styling
- backend/app/api/settings.py - Return masked qobuz_email in response

---

## [0.1.27] - 2026-01-25

### Changed - Host Path Display
- Settings now displays actual host paths (e.g., /Volumes/media/...) instead of container paths
- Added MUSIC_PATH_HOST env var for path translation
- Browse modal shows host paths for clarity

### Files Modified
- frontend/src/pages/Settings.jsx - Path translation between host/container
- backend/app/config.py - Added music_path_host setting
- backend/app/api/settings.py - Include music_path_host in response
- docker-compose.yml - Pass MUSIC_PATH_HOST to container
- .env - Added MUSIC_PATH_HOST

---

## [0.1.26] - 2026-01-25

### Added - Dual Library Path Settings
- Music Library Path setting (master library location)
- User Libraries Path setting (per-user symlink location)
- Both paths have Browse button and independent Save

### Files Modified
- frontend/src/pages/Settings.jsx - Two path settings with shared browser modal
- backend/app/api/settings.py - Added music_users to SettingsUpdate schema

---

## [0.1.25] - 2026-01-25

### Fixed - Settings & Login UI
- Settings library path input now editable (was disabled)
- Added directory browser modal for path selection
- Login page redesigned with Braun Design Language
- Improved spacing, typography, and visual hierarchy on login

### Added
- GET /settings/browse endpoint for filesystem browsing (admin only)
- PUT /settings now supports music_library path updates

### Files Modified
- frontend/src/pages/Login.jsx - Braun design cleanup
- frontend/src/pages/Settings.jsx - Editable path input + browse modal
- frontend/src/services/api.js - browseDirectory API function
- frontend/src/styles/design-system.css - Login styles, path input group, browser styles
- backend/app/api/settings.py - Browse endpoint, music_library in update schema

---

## [0.1.24] - 2026-01-25

### Added - Final Audit Completion
- Album status tracking: `status` column (complete, incomplete, pending)
- Album missing tracks: `missing_tracks` JSON column for incomplete album handling
- BackupHistory model and table for tracking backup operations
- Admin endpoints per contracts.md:
  - GET /admin/health - Library health report with stats
  - GET /admin/activity - All activity logs with filtering
  - POST /admin/integrity/verify - Trigger integrity verification
  - GET /admin/backup/history - Backup operation history
  - POST /admin/backup/trigger - Manual backup trigger
- run_backup Celery task for async backup operations

### Fixed
- Updated phase-5-admin.md checklist to mark all items complete

### Files Created
- alembic/versions/005_album_status_backup_history.py - Migration for new columns/table
- app/models/backup_history.py - BackupHistory model

### Files Modified
- app/models/album.py - Added status, missing_tracks columns
- app/models/__init__.py - Export BackupHistory
- app/api/admin.py - Added health, activity, integrity, backup endpoints
- app/tasks/maintenance.py - Added run_backup task
- docs/phases/phase-5-admin.md - Marked checklist complete

---

## [0.1.23] - 2026-01-25

### Fixed - Phase 6 Polish
- Added /live endpoint to nginx.conf for complete health check coverage
- CORS now configurable via CORS_ORIGINS env var (was hardcoded to "*")
- Added CORS_ORIGINS to .env.example with documentation

### Files Modified
- nginx/nginx.conf - Added /live location block
- backend/app/main.py - CORS origins from environment variable
- .env.example - Added CORS_ORIGINS setting

---

## [0.1.22] - 2026-01-25

### Added - Phase 6 Deployment and Polish
- Production Docker compose (docker-compose.prod.yml) with resource limits
- Production Dockerfiles with multi-stage builds (Dockerfile.prod)
- Nginx reverse proxy with SSL/TLS, rate limiting, WebSocket support
- Database backup/restore scripts (backups/backup.sh, backups/restore.sh)
- Enhanced health check endpoint with database, Redis, filesystem checks
- Readiness and liveness probe endpoints (/ready, /live)
- Logging configuration with file rotation (app/logging_config.py)
- Environment validation script (scripts/validate_env.py)
- Makefile with deployment commands (dev, prod, backup, restore, SSL)
- End-to-end tests (tests/test_e2e.py)

### Phase 6 Status - COMPLETE
- Production Docker configuration: complete
- Nginx reverse proxy: complete
- SSL/TLS setup: complete (self-signed generation via make ssl-generate)
- Database backups: complete (backup.sh, restore.sh)
- Health checks: complete (/health, /ready, /live)
- Logging configuration: complete (console + rotating file)
- Environment validation: complete
- Final testing: complete (E2E tests added)

### Files Created (11 files)
- docker-compose.prod.yml - Production Docker Compose
- backend/Dockerfile.prod - Production backend Dockerfile
- frontend/Dockerfile.prod - Production frontend Dockerfile
- nginx/nginx.conf - Nginx reverse proxy configuration
- backups/backup.sh - Database backup script
- backups/restore.sh - Database restore script
- backend/app/api/health.py - Enhanced health endpoints
- backend/app/logging_config.py - Logging configuration
- scripts/validate_env.py - Environment validation
- Makefile - Deployment commands
- backend/tests/test_e2e.py - End-to-end tests

### Files Modified (4 files)
- backend/app/main.py - Include health router, setup logging
- backend/app/config.py - Added log_path setting
- backend/tests/conftest.py - Added test_artist, test_album, test_track fixtures
- .env.example - Updated LOG_PATH documentation

---

## [0.1.21] - 2026-01-25

### Added - Phase 5 Audit Fix
- MetadataEditor.jsx component for editing album/track/artist metadata
- Supports all three entity types with appropriate form fields

### Files Created
- frontend/src/components/MetadataEditor.jsx

---

## [0.1.20] - 2026-01-25

### Added - Phase 5 Admin Features
- User management API (CRUD): /admin/users endpoints
- Pending review queue: /import/review endpoints with approve/reject
- Export service: /exports endpoints with FLAC/MP3/both formats
- TorrentLeech integration: /tl/check and /tl/upload endpoints
- Lidarr integration: /lidarr endpoints for artist requests
- Bandcamp sync: Collection download via bandcamp-collection-downloader
- Metadata editing: /metadata endpoints for albums/tracks/artists
- Artwork upload: /albums/{id}/artwork PUT with original backup
- Settings management: /settings GET/PUT with connection tests

### Phase 5 Status - COMPLETE
- User management (CRUD): complete
- Pending review queue: complete
- Export service (FLAC/MP3/both): complete
- TorrentLeech check/upload: complete
- Lidarr artist request/queue: complete
- Bandcamp collection sync: complete
- Metadata editing: complete
- Custom artwork upload: complete
- Settings page API: complete
- MetadataEditor.jsx: complete

### Files Created (19 files)
- frontend/src/components/MetadataEditor.jsx - Metadata editing modal
- app/api/admin.py - User management endpoints
- app/api/review.py - Pending review queue endpoints
- app/api/exports.py - Export endpoints
- app/api/torrentleech.py - TorrentLeech endpoints
- app/api/lidarr.py - Lidarr endpoints
- app/api/artwork.py - Artwork upload endpoints
- app/api/metadata.py - Metadata editing endpoints
- app/api/settings.py - Settings endpoints
- app/integrations/torrentleech.py - TorrentLeech API client
- app/integrations/lidarr.py - Lidarr API client
- app/integrations/bandcamp.py - Bandcamp sync client
- app/services/torrent.py - Torrent creation service
- app/services/export_service.py - Export service
- app/models/export.py - Export model
- app/schemas/review.py - Review schemas
- app/schemas/export.py - Export schemas
- app/tasks/exports.py - Export Celery tasks
- alembic/versions/004_phase5_exports.py - Export table migration

### Files Modified (7 files)
- app/api/__init__.py - Include new routers
- app/config.py - Added bandcamp_cookies setting
- app/models/__init__.py - Export export model
- app/integrations/__init__.py - Export new integrations
- app/services/__init__.py - Export new services
- app/tasks/__init__.py - Export new tasks
- app/tasks/downloads.py - Added sync_bandcamp_task
- frontend/src/services/api.js - Added new API endpoints

---

## [0.1.19] - 2026-01-25

### Fixed
- Added dark mode toggle to Sidebar footer
- Theme persists via localStorage (barbossa-theme)
- System preference detection on first load

### Files Created
- src/stores/theme.js - Zustand theme store with persistence

### Files Modified
- src/components/Sidebar.jsx - Added theme toggle button with sun/moon icons
- src/index.jsx - Initialize theme on app load
- src/styles/design-system.css - Theme toggle button styles

---

## [0.1.18] - 2026-01-25

### Added - Phase 4 Frontend GUI
- Complete React frontend with Vite build setup
- API client with JWT auth interceptors (services/api.js)
- WebSocket service for real-time updates (services/websocket.js)
- Zustand stores: auth, notifications, downloads, player
- Login page with auth state persistence
- Master Library page with A-Z navigation filter
- User Library page with search filter
- Downloads page with Qobuz search and URL download
- Settings page (admin): General, Users, Sources, Review Queue, Backup tabs
- AlbumCard with heart (bottom-left), trash (top-left, 1s delay), source badge (bottom-right)
- AlbumModal with track list and quality display
- TrackRow component: [Heart] [Track#] [Title] [Source] [Quality]
- Persistent audio Player bar at bottom
- Toast notifications via ToastContainer
- SearchBar with debounce
- Layout with Sidebar navigation

### Phase 4 Status - COMPLETE
- Project setup (Vite + React): complete
- API client with auth: complete
- WebSocket connection: complete
- Zustand stores: complete (4 stores)
- All 5 pages functional: Login, Library, UserLibrary, Downloads, Settings
- Album detail modal: complete
- TrackRow component: complete (per contracts.md spec)
- AlbumCard icon positions: complete (per contracts.md spec)
- Trash icon 1-second hover delay: complete
- Persistent audio player: complete
- Toast notifications: complete
- Dark mode support: via design-system.css

### Files Created (24 files)
- vite.config.js
- index.html
- src/index.jsx
- src/App.jsx
- src/services/api.js
- src/services/websocket.js
- src/stores/auth.js
- src/stores/notifications.js
- src/stores/downloads.js
- src/stores/player.js
- src/utils/debounce.js
- src/components/Layout.jsx
- src/components/Header.jsx
- src/components/Sidebar.jsx
- src/components/AlbumGrid.jsx
- src/components/AlbumCard.jsx
- src/components/AlbumModal.jsx
- src/components/Player.jsx
- src/components/ToastContainer.jsx
- src/components/TrackRow.jsx
- src/components/SearchBar.jsx
- src/pages/Login.jsx
- src/pages/Library.jsx
- src/pages/UserLibrary.jsx
- src/pages/Downloads.jsx
- src/pages/Settings.jsx

---

## [0.1.17] - 2026-01-25

### Added - Phase 3 Real-time Updates
- WebSocket connection manager with per-user tracking, heartbeat, admin broadcasts
- WebSocket API endpoint (/ws) with JWT authentication
- Activity service with async broadcasts for hearts, imports, library updates
- Watch folder service for automatic album imports (app/watcher.py)
- Plex integration for auto-scan after imports (app/integrations/plex.py)
- Celery beat scheduler with periodic tasks
- Import tasks: scan_import_folder, process_import, process_review
- Maintenance tasks: cleanup_old_downloads, verify_integrity, update_album_stats
- Additional maintenance: cleanup_orphan_symlinks, update_library_stats, cleanup_empty_folders
- WebSocket tests (19 tests in test_websocket.py)
- Migration 003_phase3_updates for pending_review notes field

### Phase 3 Status - COMPLETE
- WebSocket connection manager: complete (per-user, heartbeat, admin)
- Download progress broadcast: complete
- Activity feed broadcasts: complete (hearts, imports, library updates)
- Watch folder service: complete
- Celery beat scheduler: complete (7 scheduled tasks)
- Plex auto-scan integration: complete
- Connection heartbeat/reconnection: complete
- All 65 tests passing

### Files Created (7 files)
- app/api/websocket.py
- app/watcher.py
- app/tasks/imports.py
- app/tasks/maintenance.py
- app/integrations/plex.py
- tests/test_websocket.py
- alembic/versions/003_phase3_updates.py

### Files Modified (8 files)
- app/websocket.py - Enhanced with per-user tracking, heartbeat, admin broadcasts
- app/services/activity.py - Added async broadcast methods
- app/worker.py - Added beat schedule and task includes
- app/config.py - Added plex_enabled, plex_auto_scan settings
- app/main.py - Include WebSocket router
- app/api/__init__.py - Export ws_router
- app/models/pending_review.py - Added notes field
- app/services/import_service.py - Added async import_album method
- tests/conftest.py - Added auth_token, admin_token fixtures
- tests/test_downloads.py - Fixed test for new API

---

## [0.1.16] - 2026-01-25

### Fixed
- Auth test assertions now accept 401 or 403 (both valid for "requires auth")
- All 46 tests passing in Docker

---

## [0.1.15] - 2026-01-25

### Added - Phase 2 Download Pipeline
- Streamrip integration for Qobuz downloads (app/integrations/streamrip.py)
- yt-dlp integration for YouTube, Bandcamp, Soundcloud (app/integrations/ytdlp.py)
- Beets integration for auto-tagging (app/integrations/beets.py)
- ExifTool integration for quality metadata (app/integrations/exiftool.py)
- Download service with duplicate detection and quality comparison
- Import service for album indexing with normalized name matching
- Celery worker setup for background downloads (app/worker.py)
- Download tasks with progress tracking (app/tasks/downloads.py)
- Download API endpoints: search Qobuz, download from URL, queue management
- WebSocket manager for real-time progress updates
- ImportHistory model for duplicate detection
- PendingReview model for unidentified imports
- Migration 002_phase2_downloads for new tables
- Download tests (test_downloads.py)

### Phase 2 Status - AUDIT COMPLETE
- Streamrip integration: complete
- yt-dlp integration: complete
- Beets auto-tagging: complete
- ExifTool quality extraction: complete
- Download queue (Celery tasks): complete
- Duplicate detection: complete
- Quality comparison logic: complete
- WebSocket progress: basic setup (full in Phase 3)
- All checklist items verified
- All exit criteria met
- 14 tests passing

### Files Created (14 files)
- app/integrations/__init__.py
- app/integrations/streamrip.py
- app/integrations/ytdlp.py
- app/integrations/beets.py
- app/integrations/exiftool.py
- app/services/download.py
- app/services/import_service.py
- app/tasks/__init__.py
- app/tasks/downloads.py
- app/api/downloads.py
- app/schemas/download.py
- app/worker.py
- app/websocket.py
- app/models/import_history.py
- app/models/pending_review.py
- alembic/versions/002_phase2_downloads.py
- tests/test_downloads.py

---

## [0.1.14] - 2026-01-25

### Added - Phase 1 Completion
- Alembic database migrations setup (alembic.ini, env.py, script.py.mako)
- Initial migration (001_initial_schema.py) with all Phase 1 tables
- CLI module using Typer with auth, library, and admin subcommands
- CLI auth: login, logout, whoami with token storage
- CLI library: artists, albums, tracks, search, heart, unheart, my-library
- CLI admin: create-user, list-users, delete-user, seed, db-init, rescan
- CLI entry point via app/__main__.py
- CLI tests (test_cli.py)
- Added typer, rich, bcrypt==4.0.1 to requirements.txt

### Fixed
- ActivityLog model uses JSON/String instead of JSONB/INET for SQLite test compatibility
- Fixed deprecation warning: Query regex -> pattern
- Dockerfile now includes tests/ and alembic/ directories

### Phase 1 Status
- All checklist items complete (100%)
- All 26 tests passing
- Database migrations: working
- Seed data: via CLI admin seed command
- CLI wrapper: full implementation

---

## [0.1.13] - 2026-01-25

### Added - Phase 1 Core Backend Implementation
- Complete FastAPI application structure in backend/app/
- Database layer: config.py, database.py with SQLAlchemy setup
- SQLAlchemy models: User, Artist, Album, Track, ActivityLog, Download, user_albums, user_tracks
- Pydantic schemas: user, artist, album, track, common responses
- Core services: AuthService, LibraryService, UserLibraryService, SymlinkService, QualityService, ActivityService
- API endpoints: auth (login/logout/me), library (artists/albums/tracks/search), streaming (track/artwork)
- User library endpoints: heart/unheart albums and tracks with symlink management
- JWT authentication with bcrypt password hashing
- Dependencies: get_current_user, require_admin
- Utility modules: normalize.py (text normalization), paths.py (path manipulation)
- Test suite: conftest.py with fixtures, test_auth.py, test_library.py

### Files Created (33 Python files)
- app/__init__.py, main.py, config.py, database.py, dependencies.py
- app/api/__init__.py, auth.py, library.py, streaming.py
- app/models/__init__.py, user.py, artist.py, album.py, track.py, user_library.py, activity.py, download.py
- app/schemas/__init__.py, user.py, artist.py, album.py, track.py, common.py
- app/services/__init__.py, auth.py, library.py, user_library.py, symlink.py, quality.py, activity.py
- app/utils/__init__.py, normalize.py, paths.py
- tests/__init__.py, conftest.py, test_auth.py, test_library.py

---

## [0.1.12] - 2026-01-24

### Fixed
- Aligned docs and API spec on endpoints, artwork/stream routes, and auth token naming
- Documented downloads as temporary staging with auto-fallback search to Qobuz
- Added playlist search support in Downloads and clarified search behavior
- Corrected phase-0 checklist status and open questions list
- Set playlist scope to M3U export only for now
- Locked decisions for multi-disc handling, compilation handling, and mobile app scope

## [0.1.11] - 2026-01-24

### Fixed
- Comprehensive audit of all phase guides against contracts.md requirements

### Added to Phase 4 (GUI)
- TrackRow component with format: [Heart] [Track #] [Title] [Source Badge] [Quality]
- SearchBar component with debounce
- Login page
- UserLibrary page
- Settings page with tabs (General, Users, Sources, Review Queue, Backup)
- AlbumCard icon positions per spec (Heart bottom-left, Trash top-left, Source bottom-right)
- Trash icon 1-second hover delay per spec
- Source badge on album cards
- AddUserModal component
- debounce utility function

### Audit Results
- All 6 phases now complete with no missing requirements
- Icon positions match contracts.md exactly
- Track-level heart UI implemented
- All referenced components now defined

---

## [0.1.10] - 2026-01-23

### Added
- Complete Phase 0 foundation files
- In-depth coding guides for all 6 implementation phases

### New Files
- .env.example - Environment configuration template
- backend/Dockerfile - Development Dockerfile
- backend/requirements.txt - Python dependencies
- frontend/Dockerfile - Frontend Dockerfile
- frontend/package.json - Frontend dependencies
- frontend/nginx.conf - Nginx configuration for SPA
- docs/phases/phase-1-core.md - Core backend implementation guide
- docs/phases/phase-2-downloads.md - Download pipeline guide
- docs/phases/phase-3-realtime.md - WebSocket and Celery guide
- docs/phases/phase-4-gui.md - React frontend guide
- docs/phases/phase-5-admin.md - Admin features guide
- docs/phases/phase-6-deploy.md - Deployment and operations guide

### Phase Guide Contents
- Phase 1: Database models, auth service, library service, FastAPI setup
- Phase 2: Streamrip, yt-dlp, beets, exiftool integrations, duplicate detection
- Phase 3: WebSocket manager, activity service, watch folder, Celery config
- Phase 4: React setup, Zustand stores, components, pages, player
- Phase 5: User management, review queue, TorrentLeech, exports, Lidarr
- Phase 6: Production Docker, nginx, SSL, backups, health checks, monitoring

---

## [0.1.9] - 2026-01-23

### Added
- Complete Braun Design Language design system for frontend
- API-first architecture blueprint with CLI commands
- Comprehensive phased implementation blueprint

### New Files
- frontend/src/styles/design-system.css - Full CSS design system (23 sections, 1200+ lines)
- docs/BLUEPRINT.md - Master implementation plan with 6 phases

### Blueprint Contents
- Requirements audit (feature checklist, interface audit, settings audit)
- 6-phase implementation plan (Foundation through Deployment)
- Data models (9 tables defined)
- API contract (25+ endpoints)
- CLI contract (30+ commands)
- Integration matrix (7 sources)
- Open questions (9 items requiring decision)
- Risk assessment (6 risks identified)
- Acceptance criteria (MVP + Full Release)

### Design System Features
- Braun Linear typeface integration (5 weights)
- 8pt spacing grid system
- Light/dark mode color tokens
- Component specs: buttons, inputs, cards, track rows, player bar
- Braun audit fixes: no delayed reveals, toasts instead of modals
- Max 8px border radius per Braun spec
- Functional colors only (success, warning, error, accent)

### Architecture Decision
- API-first approach selected over CLI-first
- All operations testable via curl before GUI exists
- CLI wraps API calls for scriptability

---

## [0.1.8] - 2026-01-23

### Added
- Complete operational documentation for production deployment

### New Documentation
- docs/rclone-backup.md - Cloud backup with rclone (S3, B2, Google Drive, NAS)
- docs/websocket-implementation.md - Full WebSocket server/client implementation
- docs/cicd-pipeline.md - GitHub Actions workflows, Docker builds, deployment
- docs/monitoring-logging.md - Prometheus metrics, ELK stack, Grafana dashboards
- docs/rate-limiting.md - API protection, concurrent limits, external API throttling
- docs/playlist-sync.md - M3U export, Last.fm import, Spotify/Apple workarounds

### Research Status
- All 14 integration docs now complete
- Ready for implementation

---

## [0.1.7] - 2026-01-23

### Added
- Simplified search architecture: Search Library / Search Qobuz / Search Lidarr
- Universal URL handler via yt-dlp (YouTube, Soundcloud, Bandcamp free, 1800+ sites)
- Bandcamp purchase sync via bandcamp-collection-downloader
- Soundcloud support documented (via streamrip)
- Plex API integration with path-specific scanning
- Custom artwork upload on import and album edit

### New Documentation
- docs/plex-integration.md - Full Plex API reference, token setup, scan endpoints
- docs/bandcamp-integration.md - Purchase sync + free track handling

### Updated Documentation
- docs/streamrip-integration.md - Added Soundcloud section
- docs/ytdlp-integration.md - Clarified as universal URL handler
- contracts.md - Simplified search, custom artwork, updated source priority

---

## [0.1.6] - 2026-01-23

### Added
- Multi-source download architecture (Qobuz > Lidarr > Import > yt-dlp)
- Lidarr API integration for automated downloads and gap filling
- yt-dlp fallback for rare/live/unreleased content
- Import watch folder with review queue for unidentified content
- User library export (FLAC full quality + MP3 portable)
- Activity log tracking all imports, hearts, deletions
- Backup integration (local, NAS, rclone)
- Source tracking in database (provenance)
- Incomplete album detection and gap filling
- Plex API auto-scan on import
- Integrity verification with checksums
- Mixed-source album support (best quality per track)

### Changed
- Database schema expanded for source tracking, activity log, checksums
- Import pipeline now supports multiple sources with quality merging
- Download UI shows source options (Qobuz/Lidarr/YouTube)

### New Documentation
- docs/lidarr-integration.md
- docs/ytdlp-integration.md

---

## [0.1.5] - 2026-01-23

### Changed
- Preview player now uses react-h5-audio-player library instead of custom implementation
- Simpler audio store (player handles its own state)
- Added custom styling example for player

---

## [0.1.4] - 2026-01-23

### Changed
- Refocused project scope: Barbossa is a download manager + library organizer, NOT a streaming service
- Clarified that Plex/Plexamp handles actual listening
- Added preview player for checking if songs work
- Simplified architecture docs to match actual requirements

### Updated
- about.md - Clear "what it is" vs "what it's not"
- contracts.md - Cleaner specs with proper tables and code examples
- techguide.md - Complete API endpoints, services, and frontend components

---

## [0.1.3] - 2026-01-23

### Added
- docs/exiftool-integration.md - CLI reference, Python integration, quality comparison logic

### Key Findings
- FLAC tags: SampleRate, BitsPerSample, Channels (from StreamInfo block)
- MP3 tags: AudioBitrate, SampleRate, ChannelMode (from MPEG header)
- PyExifTool for Python integration (requires exiftool 12.15+)
- Quality comparison: sample_rate > bit_depth > file_size priority

---

## [0.1.2] - 2026-01-23

### Added
- docs/beets-integration.md - Complete config, path templates, plugins, CLI reference

### Key Findings
- Path format: `$albumartist/$album ($year)/$track - $title` for Plex
- Always use `$albumartist` not `$artist` (keeps compilations together)
- Essential plugins: musicbrainz, fetchart, embedart, lyrics, scrub
- `%aunique{}` function disambiguates duplicate album names

---

## [0.1.1] - 2026-01-23

### Added
- docs/streamrip-integration.md - Full CLI reference, quality tiers, Python API notes
- docs/torrentleech-integration.md - Upload/Search API docs, mktorrent setup, NFO generation

### Resolved
- Streamrip search: Must force user to select type (artist/track/album)
- TorrentLeech search API confirmed: Returns 0/1 for pre-existence check
- Deduplication: Streamrip handles its own, Barbossa adds quality-aware layer

---

## [0.1.0] - 2026-01-23

### Added
- Initial project specification
- about.md with project overview
- contracts.md with detailed requirements
- Core feature definitions
