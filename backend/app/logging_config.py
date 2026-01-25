"""Logging configuration for Barbossa."""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os

from app.config import settings


def setup_logging():
    """Configure application logging."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    handlers = [console_handler]

    # File handler (if log path configured)
    log_path = os.getenv('LOG_PATH', '')
    if log_path:
        log_file = Path(log_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers
    )

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get logger for module."""
    return logging.getLogger(name)
