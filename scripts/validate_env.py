#!/usr/bin/env python3
"""Validate environment configuration before startup."""
import os
import sys
from pathlib import Path


def validate():
    """Validate all required environment variables."""
    errors = []
    warnings = []

    # Required variables
    required = [
        ("DB_PASSWORD", "Database password"),
        ("JWT_SECRET", "JWT secret key"),
        ("MUSIC_PATH", "Music library path"),
    ]

    for var, description in required:
        if not os.getenv(var):
            errors.append(f"Missing required: {var} ({description})")

    # Check DB password is not default
    db_password = os.getenv("DB_PASSWORD", "")
    if db_password == "barbossa":
        warnings.append("DB_PASSWORD is set to default value - change for production")

    # Check JWT secret strength
    jwt_secret = os.getenv("JWT_SECRET", "")
    if jwt_secret and len(jwt_secret) < 32:
        warnings.append("JWT_SECRET should be at least 32 characters")
    if jwt_secret and "change" in jwt_secret.lower():
        warnings.append("JWT_SECRET appears to be a placeholder - generate a real secret")

    # Check music path exists
    music_path = os.getenv("MUSIC_PATH")
    if music_path:
        path = Path(music_path)
        if not path.exists():
            warnings.append(f"MUSIC_PATH does not exist: {music_path}")
        elif not path.is_dir():
            errors.append(f"MUSIC_PATH is not a directory: {music_path}")

    # Optional integrations - check pairs
    if os.getenv("QOBUZ_EMAIL") and not os.getenv("QOBUZ_PASSWORD"):
        warnings.append("QOBUZ_EMAIL set but QOBUZ_PASSWORD missing")

    if os.getenv("LIDARR_URL") and not os.getenv("LIDARR_API_KEY"):
        warnings.append("LIDARR_URL set but LIDARR_API_KEY missing")

    if os.getenv("PLEX_URL") and not os.getenv("PLEX_TOKEN"):
        warnings.append("PLEX_URL set but PLEX_TOKEN missing")

    # Check SSL certificates exist
    ssl_cert = Path("nginx/ssl/cert.pem")
    ssl_key = Path("nginx/ssl/key.pem")
    if not ssl_cert.exists():
        warnings.append("SSL certificate not found: nginx/ssl/cert.pem")
    if not ssl_key.exists():
        warnings.append("SSL key not found: nginx/ssl/key.pem")

    # Check backup directory writable
    backup_dir = Path("backups")
    if backup_dir.exists() and not os.access(backup_dir, os.W_OK):
        warnings.append("Backups directory not writable")

    # Report results
    print("=" * 60)
    print("Barbossa Environment Validation")
    print("=" * 60)

    if errors:
        print("\nERRORS:")
        for error in errors:
            print(f"  [X] {error}")

    if warnings:
        print("\nWARNINGS:")
        for warning in warnings:
            print(f"  [!] {warning}")

    if not errors and not warnings:
        print("\n  All checks passed.")

    print("\n" + "=" * 60)

    if errors:
        print("RESULT: Configuration INVALID - fix errors before starting")
        sys.exit(1)

    if warnings:
        print("RESULT: Configuration valid with warnings")
    else:
        print("RESULT: Configuration valid")

    sys.exit(0)


if __name__ == "__main__":
    validate()
