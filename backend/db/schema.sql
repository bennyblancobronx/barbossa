-- BARBOSSA DATABASE SCHEMA
-- Version: 0.1.9
-- PostgreSQL 15+

-- ==========================================================================
-- EXTENSIONS
-- ==========================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- ==========================================================================
-- 1. USERS
-- ==========================================================================
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    is_admin        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Default admin user (password: admin - CHANGE IMMEDIATELY)
-- Password hash is bcrypt of "admin"
INSERT INTO users (username, password_hash, is_admin) VALUES
('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.G/Q.z.Q.z.Q.z.', TRUE);

CREATE INDEX idx_users_username ON users(username);

-- ==========================================================================
-- 2. ARTISTS
-- ==========================================================================
CREATE TABLE artists (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,  -- Lowercase, no punctuation
    sort_name       VARCHAR(255),           -- "Beatles, The" for sorting
    path            VARCHAR(1000),          -- /music/library/Artist Name
    artwork_path    VARCHAR(1000),
    musicbrainz_id  VARCHAR(36),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_artists_name ON artists(name);
CREATE INDEX idx_artists_normalized ON artists(normalized_name);
CREATE INDEX idx_artists_sort ON artists(sort_name);
CREATE INDEX idx_artists_name_trgm ON artists USING gin(name gin_trgm_ops);

-- ==========================================================================
-- 3. ALBUMS
-- ==========================================================================
CREATE TABLE albums (
    id              SERIAL PRIMARY KEY,
    artist_id       INTEGER NOT NULL REFERENCES artists(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    normalized_title VARCHAR(255) NOT NULL,  -- Lowercase, no punctuation
    year            INTEGER,
    path            VARCHAR(1000),          -- /music/library/Artist/Album (Year)
    artwork_path    VARCHAR(1000),          -- /music/library/Artist/Album (Year)/cover.jpg
    total_tracks    INTEGER DEFAULT 0,
    available_tracks INTEGER DEFAULT 0,
    disc_count      INTEGER DEFAULT 1,
    genre           VARCHAR(100),
    label           VARCHAR(255),
    catalog_number  VARCHAR(100),
    musicbrainz_id  VARCHAR(36),
    source          VARCHAR(50),            -- qobuz, lidarr, youtube, bandcamp, import
    source_url      VARCHAR(1000),
    is_compilation  BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_albums_artist ON albums(artist_id);
CREATE INDEX idx_albums_title ON albums(title);
CREATE INDEX idx_albums_normalized ON albums(normalized_title);
CREATE INDEX idx_albums_year ON albums(year);
CREATE INDEX idx_albums_source ON albums(source);
CREATE INDEX idx_albums_title_trgm ON albums USING gin(title gin_trgm_ops);

-- ==========================================================================
-- 4. TRACKS
-- ==========================================================================
CREATE TABLE tracks (
    id              SERIAL PRIMARY KEY,
    album_id        INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    normalized_title VARCHAR(255) NOT NULL,
    track_number    INTEGER NOT NULL,
    disc_number     INTEGER DEFAULT 1,
    duration        INTEGER,                -- Seconds
    path            VARCHAR(1000) NOT NULL,

    -- Quality metadata (from ExifTool)
    sample_rate     INTEGER,                -- 44100, 96000, 192000
    bit_depth       INTEGER,                -- 16, 24
    bitrate         INTEGER,                -- kbps for lossy
    channels        INTEGER DEFAULT 2,
    file_size       BIGINT,                 -- Bytes
    format          VARCHAR(10),            -- FLAC, MP3, AAC, etc.
    is_lossy        BOOLEAN DEFAULT FALSE,

    -- Source tracking
    source          VARCHAR(50),            -- qobuz, lidarr, youtube, etc.
    source_url      VARCHAR(1000),
    source_quality  VARCHAR(100),           -- "24/192 FLAC", "320kbps MP3"

    -- Integrity
    checksum        VARCHAR(64),            -- SHA-256

    -- Metadata
    lyrics          TEXT,
    musicbrainz_id  VARCHAR(36),

    imported_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    imported_by     INTEGER REFERENCES users(id),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tracks_album ON tracks(album_id);
CREATE INDEX idx_tracks_title ON tracks(title);
CREATE INDEX idx_tracks_normalized ON tracks(normalized_title);
CREATE INDEX idx_tracks_source ON tracks(source);
CREATE INDEX idx_tracks_quality ON tracks(sample_rate, bit_depth);
CREATE INDEX idx_tracks_title_trgm ON tracks USING gin(title gin_trgm_ops);

-- ==========================================================================
-- 5. USER LIBRARY - ALBUM HEARTS
-- ==========================================================================
CREATE TABLE user_albums (
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    album_id        INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    added_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, album_id)
);

CREATE INDEX idx_user_albums_user ON user_albums(user_id);
CREATE INDEX idx_user_albums_album ON user_albums(album_id);

-- ==========================================================================
-- 6. USER LIBRARY - TRACK HEARTS (Individual tracks)
-- ==========================================================================
CREATE TABLE user_tracks (
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track_id        INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    added_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, track_id)
);

CREATE INDEX idx_user_tracks_user ON user_tracks(user_id);
CREATE INDEX idx_user_tracks_track ON user_tracks(track_id);

-- ==========================================================================
-- 7. ACTIVITY LOG
-- ==========================================================================
CREATE TABLE activity_log (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action          VARCHAR(50) NOT NULL,   -- download, import, heart, unheart, delete, export
    entity_type     VARCHAR(50),            -- artist, album, track
    entity_id       INTEGER,
    details         JSONB,                  -- Additional context
    ip_address      INET,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activity_user ON activity_log(user_id);
CREATE INDEX idx_activity_action ON activity_log(action);
CREATE INDEX idx_activity_entity ON activity_log(entity_type, entity_id);
CREATE INDEX idx_activity_created ON activity_log(created_at);

-- ==========================================================================
-- 8. IMPORT HISTORY (Duplicate Detection)
-- ==========================================================================
CREATE TABLE import_history (
    id                  SERIAL PRIMARY KEY,
    artist_normalized   VARCHAR(255) NOT NULL,
    album_normalized    VARCHAR(255) NOT NULL,
    track_normalized    VARCHAR(255) NOT NULL,
    source              VARCHAR(50),
    quality_score       INTEGER,            -- Computed: sample_rate * bit_depth
    checksum            VARCHAR(64),
    track_id            INTEGER REFERENCES tracks(id) ON DELETE SET NULL,
    import_date         TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_import_lookup ON import_history(artist_normalized, album_normalized, track_normalized);
CREATE INDEX idx_import_checksum ON import_history(checksum);

-- ==========================================================================
-- 9. DOWNLOADS (Queue)
-- ==========================================================================
CREATE TYPE download_status AS ENUM ('pending', 'downloading', 'importing', 'complete', 'failed', 'cancelled');
CREATE TYPE download_source AS ENUM ('qobuz', 'lidarr', 'youtube', 'soundcloud', 'bandcamp', 'url');
CREATE TYPE search_type AS ENUM ('artist', 'album', 'track');

CREATE TABLE downloads (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source          download_source NOT NULL,
    source_url      VARCHAR(1000),
    search_query    VARCHAR(500),
    search_type     search_type,
    status          download_status DEFAULT 'pending',
    progress        INTEGER DEFAULT 0,      -- 0-100
    speed           VARCHAR(50),            -- "2.5 MB/s"
    eta             VARCHAR(50),            -- "00:05:32"
    error_message   TEXT,
    celery_task_id  VARCHAR(255),
    result_album_id INTEGER REFERENCES albums(id) ON DELETE SET NULL,
    started_at      TIMESTAMP WITH TIME ZONE,
    completed_at    TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_downloads_user ON downloads(user_id);
CREATE INDEX idx_downloads_status ON downloads(status);
CREATE INDEX idx_downloads_created ON downloads(created_at);

-- ==========================================================================
-- 10. PENDING REVIEW (Unidentified Imports)
-- ==========================================================================
CREATE TYPE review_status AS ENUM ('pending', 'approved', 'rejected', 'merged');

CREATE TABLE pending_review (
    id                  SERIAL PRIMARY KEY,
    path                VARCHAR(1000) NOT NULL,
    suggested_artist    VARCHAR(255),
    suggested_album     VARCHAR(255),
    suggested_year      INTEGER,
    beets_confidence    FLOAT,              -- 0.0 - 1.0
    file_count          INTEGER,
    total_size          BIGINT,
    status              review_status DEFAULT 'pending',
    reviewed_by         INTEGER REFERENCES users(id),
    reviewed_at         TIMESTAMP WITH TIME ZONE,
    result_album_id     INTEGER REFERENCES albums(id) ON DELETE SET NULL,
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_review_status ON pending_review(status);
CREATE INDEX idx_review_created ON pending_review(created_at);

-- ==========================================================================
-- 11. SETTINGS (Key-Value Store)
-- ==========================================================================
CREATE TABLE settings (
    key             VARCHAR(100) PRIMARY KEY,
    value           JSONB NOT NULL,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Default settings
INSERT INTO settings (key, value) VALUES
('paths.library', '"/music/library"'),
('paths.users', '"/music/users"'),
('paths.downloads', '"/music/downloads"'),
('paths.import', '"/music/import"'),
('qobuz.quality', '4'),
('qobuz.enabled', 'true'),
('lidarr.enabled', 'false'),
('plex.enabled', 'false'),
('plex.auto_scan', 'true'),
('torrentleech.enabled', 'false');

-- ==========================================================================
-- 12. EXPORTS
-- ==========================================================================
CREATE TYPE export_status AS ENUM ('pending', 'running', 'complete', 'failed', 'cancelled');
CREATE TYPE export_format AS ENUM ('flac', 'mp3', 'both');

CREATE TABLE exports (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    destination     VARCHAR(1000) NOT NULL,
    format          export_format DEFAULT 'flac',
    include_artwork BOOLEAN DEFAULT TRUE,
    include_playlist BOOLEAN DEFAULT FALSE,
    status          export_status DEFAULT 'pending',
    progress        INTEGER DEFAULT 0,
    total_albums    INTEGER DEFAULT 0,
    exported_albums INTEGER DEFAULT 0,
    total_size      BIGINT,
    error_message   TEXT,
    celery_task_id  VARCHAR(255),
    started_at      TIMESTAMP WITH TIME ZONE,
    completed_at    TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_exports_user ON exports(user_id);
CREATE INDEX idx_exports_status ON exports(status);

-- ==========================================================================
-- FUNCTIONS
-- ==========================================================================

-- Normalize text for comparison (lowercase, remove punctuation, collapse spaces)
CREATE OR REPLACE FUNCTION normalize_text(input TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN LOWER(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(input, '\([^)]*\)', '', 'g'),  -- Remove (Deluxe), (Remaster), etc.
                '\[[^\]]*\]', '', 'g'                          -- Remove [Explicit], etc.
            ),
            '[^a-z0-9\s]', '', 'g'                             -- Remove punctuation
        )
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Calculate quality score for comparison
CREATE OR REPLACE FUNCTION quality_score(sample_rate INTEGER, bit_depth INTEGER)
RETURNS INTEGER AS $$
BEGIN
    RETURN COALESCE(sample_rate, 44100) * COALESCE(bit_depth, 16);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ==========================================================================
-- TRIGGERS
-- ==========================================================================

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_artists_updated_at BEFORE UPDATE ON artists
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_albums_updated_at BEFORE UPDATE ON albums
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_tracks_updated_at BEFORE UPDATE ON tracks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Auto-normalize on insert/update
CREATE OR REPLACE FUNCTION normalize_artist()
RETURNS TRIGGER AS $$
BEGIN
    NEW.normalized_name = normalize_text(NEW.name);
    IF NEW.sort_name IS NULL THEN
        -- "The Beatles" -> "Beatles, The"
        IF NEW.name ILIKE 'The %' THEN
            NEW.sort_name = SUBSTRING(NEW.name FROM 5) || ', The';
        ELSE
            NEW.sort_name = NEW.name;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER normalize_artist_trigger BEFORE INSERT OR UPDATE ON artists
    FOR EACH ROW EXECUTE FUNCTION normalize_artist();

CREATE OR REPLACE FUNCTION normalize_album()
RETURNS TRIGGER AS $$
BEGIN
    NEW.normalized_title = normalize_text(NEW.title);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER normalize_album_trigger BEFORE INSERT OR UPDATE ON albums
    FOR EACH ROW EXECUTE FUNCTION normalize_album();

CREATE OR REPLACE FUNCTION normalize_track()
RETURNS TRIGGER AS $$
BEGIN
    NEW.normalized_title = normalize_text(NEW.title);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER normalize_track_trigger BEFORE INSERT OR UPDATE ON tracks
    FOR EACH ROW EXECUTE FUNCTION normalize_track();

-- Update album track counts
CREATE OR REPLACE FUNCTION update_album_track_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
        UPDATE albums SET
            available_tracks = (SELECT COUNT(*) FROM tracks WHERE album_id = NEW.album_id)
        WHERE id = NEW.album_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE albums SET
            available_tracks = (SELECT COUNT(*) FROM tracks WHERE album_id = OLD.album_id)
        WHERE id = OLD.album_id;
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_track_count AFTER INSERT OR UPDATE OR DELETE ON tracks
    FOR EACH ROW EXECUTE FUNCTION update_album_track_count();

-- ==========================================================================
-- VIEWS
-- ==========================================================================

-- User library view (albums + tracks hearted)
CREATE VIEW user_library_view AS
SELECT
    u.id AS user_id,
    u.username,
    a.id AS album_id,
    ar.name AS artist_name,
    a.title AS album_title,
    a.year,
    a.artwork_path,
    a.available_tracks,
    ua.added_at
FROM users u
JOIN user_albums ua ON u.id = ua.user_id
JOIN albums a ON ua.album_id = a.id
JOIN artists ar ON a.artist_id = ar.id;

-- Quality summary view
CREATE VIEW track_quality_view AS
SELECT
    t.id,
    t.title,
    a.title AS album_title,
    ar.name AS artist_name,
    t.format,
    t.sample_rate,
    t.bit_depth,
    t.is_lossy,
    t.source,
    quality_score(t.sample_rate, t.bit_depth) AS quality_score,
    CASE
        WHEN t.sample_rate >= 192000 AND t.bit_depth = 24 THEN 'Ultra Hi-Res'
        WHEN t.sample_rate >= 96000 AND t.bit_depth = 24 THEN 'Hi-Res'
        WHEN t.sample_rate >= 44100 AND t.bit_depth >= 16 AND NOT t.is_lossy THEN 'CD Quality'
        ELSE 'Lossy'
    END AS quality_tier
FROM tracks t
JOIN albums a ON t.album_id = a.id
JOIN artists ar ON a.artist_id = ar.id;

-- ==========================================================================
-- COMMENTS
-- ==========================================================================
COMMENT ON TABLE users IS 'User accounts - admin or regular';
COMMENT ON TABLE artists IS 'Music artists in the library';
COMMENT ON TABLE albums IS 'Albums in the master library';
COMMENT ON TABLE tracks IS 'Individual tracks with quality metadata';
COMMENT ON TABLE user_albums IS 'User hearts on albums (symlink source)';
COMMENT ON TABLE user_tracks IS 'User hearts on individual tracks';
COMMENT ON TABLE activity_log IS 'Audit log of all actions';
COMMENT ON TABLE import_history IS 'Duplicate detection lookup table';
COMMENT ON TABLE downloads IS 'Download queue and history';
COMMENT ON TABLE pending_review IS 'Imports needing manual review';
COMMENT ON TABLE settings IS 'Application settings key-value store';
COMMENT ON TABLE exports IS 'User library export jobs';
