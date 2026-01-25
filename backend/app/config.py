"""Application configuration from environment variables."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Database
    database_url: str = "postgresql://barbossa:barbossa@db:5432/barbossa"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Authentication
    jwt_secret: str = "change-me-in-production-use-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Music paths (container paths - /music maps to host MUSIC_PATH)
    music_library: str = "/music/artists"      # Master library: Artist/Album (Year)/tracks
    music_users: str = "/music/users"          # Per-user symlinked libraries
    music_downloads: str = "/music/downloads"  # Temp download staging
    music_import: str = "/music/import"        # Watch folder for imports
    music_export: str = "/music/export"        # Export destination
    music_database: str = "/music/database"    # Database backups

    # Host path mapping (for UI display)
    # Container /music = Host MUSIC_PATH_HOST
    music_path_host: str = "/Volumes/media/library/music"

    # Paths aliases for compatibility
    @property
    def paths_import(self) -> str:
        return self.music_import

    @property
    def paths_library(self) -> str:
        return self.music_library

    # Qobuz
    qobuz_email: str = ""
    qobuz_password: str = ""
    qobuz_quality: int = 4  # 0-4, 4 is max (24/192)
    qobuz_app_id: str = ""  # Optional: override default app_id
    qobuz_app_secret: str = ""  # Optional: for request signing

    # Lidarr
    lidarr_url: str = ""
    lidarr_api_key: str = ""

    # Plex
    plex_url: str = ""
    plex_token: str = ""
    plex_music_section: str = ""
    plex_enabled: bool = True
    plex_auto_scan: bool = True

    # TorrentLeech
    torrentleech_key: str = ""

    # Bandcamp
    bandcamp_cookies: str = ""  # Path to cookies.txt file

    # Logging
    log_level: str = "info"
    log_path: str = ""

    class Config:
        env_file = (".env", "../.env")  # Check both backend/ and parent dir
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
