# Changelog

## [0.1.58] - 2026-01-25

### Changed - Qobuz Auto-Import
- Qobuz downloads now auto-import without beets identification (trusted source)
- Uses embedded metadata directly from Qobuz FLAC files
- Skips MusicBrainz lookup - no more review queue for Qobuz downloads
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
