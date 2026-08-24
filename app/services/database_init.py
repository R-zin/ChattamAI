"""Create the database tables.

Importing this module only defines the init helpers; call :func:`init_db` (or
:func:`init_db_safe`) to create the tables. Models must be imported before
``create_all`` so they are registered on ``Base.metadata``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.services.database import Base, engine

logger = logging.getLogger(__name__)

# Repo root (…/app/services/database_init.py -> repo root) for locating alembic.ini.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _ensure_user_totp_columns() -> None:
    """Additively ALTER an existing ``user`` table for the 2FA columns.

    Fresh databases get these from ``create_all``; this is the only hand-migration
    needed until Alembic lands (DEVELOPMENT.md §9). Standard ``ADD COLUMN`` is
    safe on both SQLite and Postgres. Called under :func:`init_db_safe`, so a
    failure is logged, never fatal."""
    from sqlalchemy import inspect, text

    cols = {c["name"] for c in inspect(engine).get_columns("user")}
    with engine.begin() as conn:
        if "totp_secret" not in cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN totp_secret VARCHAR"))
        if "totp_enabled" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE user ADD COLUMN totp_enabled "
                    "BOOLEAN NOT NULL DEFAULT 0"
                )
            )


# --- Reports (T1.1/Alembic) --------------------------------------------------
def _run_alembic_upgrade() -> bool:
    """Best-effort ``alembic upgrade head``. Returns True on success.

    Looks up ``alembic.ini`` at the repo root and applies migrations to the
    engine's URL. Returns False (never raises) if Alembic isn't installed, the
    ini/scripts are missing, or the migration fails — callers then fall back to
    the idempotent ``create_all`` + ``_ensure_user_totp_columns`` path so boot
    and offline tests are unaffected.
    """
    try:
        from alembic import command
        from alembic.config import Config
    except Exception as exc:  # noqa: BLE001 - Alembic optional at runtime
        logger.info("alembic unavailable; skipping migrations: %s", exc)
        return False
    ini_path = _REPO_ROOT / "alembic.ini"
    if not ini_path.exists():
        logger.info("alembic.ini not found at %s; skipping migrations", ini_path)
        return False
    try:
        cfg = Config(str(ini_path))
        cfg.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
        command.upgrade(cfg, "head")
        return True
    except Exception as exc:  # noqa: BLE001 - fall back to create_all below
        logger.warning("alembic upgrade head failed; falling back: %s", exc)
        return False


def init_db() -> None:
    """Create all tables. Raises on failure.

    Prefers ``alembic upgrade head``; if Alembic is unavailable or the migration
    fails, falls back to the idempotent ``create_all`` + column-ensure so the
    schema is always present (and so offline tests / missing-ini still boot).
    """
    from app.services import dbmodel, report_model  # noqa: F401  (register models)

    if _run_alembic_upgrade():
        return
    Base.metadata.create_all(bind=engine)
    _ensure_user_totp_columns()


def init_db_safe() -> bool:
    """Best-effort :func:`init_db` that never raises.

    Returns True on success, False on failure. Used at app startup so a missing
    or unreachable database never breaks the RAG boot (the RAG path does not use
    the DB). Failures are logged, not propagated.
    """
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001 - deliberately swallow for RAG boot
        logger.warning("init_db skipped (database unavailable): %s", exc)
        return False
    return True


if __name__ == "__main__":
    init_db()
