# Barbossa Backend - Development Dockerfile
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libimage-exiftool-perl \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install streamrip
RUN pip install --no-cache-dir streamrip

# Install yt-dlp
RUN pip install --no-cache-dir yt-dlp

# Install beets with plugins
RUN pip install --no-cache-dir beets[fetchart,lyrics,lastgenre,chroma]

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app/ ./app/
COPY tests/ ./tests/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]
