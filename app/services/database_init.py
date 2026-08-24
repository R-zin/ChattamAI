"""Create the database tables.

Importing this module only defines the init helpers; call :func:`init_db` (or
:func:`init_db_safe`) to create the tables. Models must be imported before
``create_all`` so they are registered on ``Base.metadata``.
"""

from __future__ import annotations

import logging

from app.services.database import Base, engine

logger = logging.getLogger(__name__)


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


def init_db() -> None:
    """Create all tables (idempotent ``create_all``). Raises on failure."""
    from app.services import dbmodel  # noqa: F401  (register models on Base)

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
