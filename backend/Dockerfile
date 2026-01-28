# Barbossa Backend Dockerfile
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Python dependencies (cached layer - only rebuilds when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY config/ ./config/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Create music directory structure
RUN mkdir -p /music/artists /music/users /music/downloads /music/import/pending /music/import/complete /music/export /music/database

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
