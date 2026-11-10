#!/usr/bin/env bash
set -e

# Target data directories
KBR_TARGET="${KBR_DATA_DIR:-/app/data/kbr}"
INDEX_TARGET="${INDEX_DIR:-/app/data/index}"
DB_DIR="$(dirname "${DATABASE_URL#sqlite:////}")"

# Verify write permission to data directory. When Azure Container Apps mounts
# an external volume (EmptyDir / AzureFile) at /app/data, it may default to root ownership.
# If not writable by the current non-root user, fallback gracefully to /tmp/chattamai.
if ! mkdir -p "$KBR_TARGET" 2>/dev/null || ! mkdir -p "$INDEX_TARGET" 2>/dev/null || ! mkdir -p "$DB_DIR" 2>/dev/null; then
    echo "Warning: Configured data directories are not writable by user $(whoami) (UID $(id -u))."
    echo "Falling back to /tmp/chattamai data directory for runtime storage..."
    export KBR_DATA_DIR="/tmp/chattamai/kbr"
    export INDEX_DIR="/tmp/chattamai/index"
    export DATABASE_URL="sqlite:////tmp/chattamai/chattamai.db"
    mkdir -p "$KBR_DATA_DIR" "$INDEX_DIR"
fi

# Apply database migrations if alembic is available
if [ -f "alembic.ini" ]; then
    echo "Applying database migrations..."
    alembic upgrade head || echo "Warning: Alembic migration failed or skipped; continuing startup..."
fi

echo "Starting ChattamAI on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
