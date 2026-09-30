#!/usr/bin/env bash
set -e

# Ensure data directories exist
mkdir -p "${KBR_DATA_DIR:-/app/data/kbr}"
mkdir -p "${INDEX_DIR:-/app/data/index}"
mkdir -p "$(dirname "${DATABASE_URL#sqlite:////}")" 2>/dev/null || true

# Apply database migrations if alembic is available
if [ -f "alembic.ini" ]; then
    echo "Applying database migrations..."
    alembic upgrade head || echo "Warning: Alembic migration failed or skipped; continuing startup..."
fi

echo "Starting ChattamAI on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
