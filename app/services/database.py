import os
from typing import Any, Dict

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def normalize_database_url(url: str) -> str:
    """Return ``url`` with Postgres schemes mapped to the psycopg (v3) driver.

    Supabase and most hosts hand out ``postgres://`` or ``postgresql://`` URIs.
    SQLAlchemy would pick psycopg2 for those, which is not installed, so rewrite
    them to ``postgresql+psycopg://``. Other URLs (SQLite, an explicit driver)
    are returned unchanged.
    """
    url = (url or "").strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def engine_kwargs(url: str) -> Dict[str, Any]:
    """Engine options per backend."""
    if url.startswith("sqlite"):
        # Required for SQLite when sharing the connection across threads (FastAPI).
        return {"connect_args": {"check_same_thread": False}}
    return {
        # Drop dead connections (pooler restarts, idle timeouts) transparently.
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 5,
        "connect_args": {"connect_timeout": 10},
    }


# Default to a local SQLite file so this module imports cleanly without any
# configuration. Set DATABASE_URL to point at a real database (e.g. Supabase).
DATABASE_URL = normalize_database_url(
    os.environ.get("DATABASE_URL", "sqlite:///./chattamai.db")
)

engine = create_engine(DATABASE_URL, **engine_kwargs(DATABASE_URL))

SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)

Base = declarative_base()
