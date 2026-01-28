#!/bin/bash
set -e

# Run database migrations (only for the API server, not worker/beat/watcher)
if [ "$1" = "uvicorn" ]; then
    echo "Running database migrations..."
    python -c "
from app.database import engine, Base
from app.models import *
Base.metadata.create_all(bind=engine)
print('Database tables verified.')
" 2>&1 || echo "Warning: migration check failed, continuing..."
fi

exec "$@"
