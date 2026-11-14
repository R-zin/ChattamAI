#!/usr/bin/env bash
set -e

# Target data locations
KBR_TARGET="${KBR_DATA_DIR:-/app/data/kbr}"
INDEX_TARGET="${INDEX_DIR:-/app/data/index}"

# True when we can create AND write a file in $1 (mkdir -p alone succeeds on an
# existing root-owned directory, so it proves nothing about writability).
dir_writable() {
    mkdir -p "$1" 2>/dev/null || return 1
    local probe="$1/.write-probe.$$"
    if ( : > "$probe" ) 2>/dev/null; then
        rm -f "$probe"
        return 0
    fi
    return 1
}

# Directory holding the SQLite file, or empty when DATABASE_URL is not SQLite.
# sqlite:////abs/path.db -> /abs ; sqlite:///./rel.db -> ./
DB_DIR=""
case "${DATABASE_URL:-}" in
    sqlite:///*)
        DB_PATH="${DATABASE_URL#sqlite:///}"
        DB_DIR="$(dirname "$DB_PATH")"
        ;;
esac

# When Azure Container Apps mounts an external volume (EmptyDir / AzureFile) at
# /app/data it may be root-owned and unwritable for this non-root user. Fall
# back to /tmp so the app still boots (data then lasts only for the container).
unwritable=""
dir_writable "$KBR_TARGET" || unwritable="$unwritable $KBR_TARGET"
dir_writable "$INDEX_TARGET" || unwritable="$unwritable $INDEX_TARGET"
if [ -n "$DB_DIR" ]; then
    dir_writable "$DB_DIR" || unwritable="$unwritable $DB_DIR"
fi

if [ -n "$unwritable" ]; then
    echo "Warning: not writable by $(whoami) (UID $(id -u)):$unwritable"
    echo "Falling back to /tmp/chattamai (data will NOT persist across restarts)."
    export KBR_DATA_DIR="/tmp/chattamai/kbr"
    export INDEX_DIR="/tmp/chattamai/index"
    mkdir -p "$KBR_DATA_DIR" "$INDEX_DIR"
    if [ -n "$DB_DIR" ]; then
        export DATABASE_URL="sqlite:////tmp/chattamai/chattamai.db"
    fi
    # KBR documents are re-seeded from the image into the new KBR_DATA_DIR by
    # the app at startup (see app/bootstrap.py).
fi

# Apply database migrations (the single place migrations run).
if [ -f "alembic.ini" ]; then
    echo "Applying database migrations..."
    alembic upgrade head || echo "Warning: Alembic migration failed or skipped; continuing startup..."
fi

echo "Starting ChattamAI on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
