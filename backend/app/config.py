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

    # Music paths
    music_library: str = "/music/library"
    music_users: str = "/music/users"
    music_downloads: str = "/music/downloads"
    music_import: str = "/music/import"
    music_export: str = "/music/export"

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
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
