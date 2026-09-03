"""Alembic environment for ChattamAI.

Resolves the database URL from the application's own engine configuration
(``app.services.database.DATABASE_URL``) rather than duplicating a DSN in
``alembic.ini``, so setting ``DATABASE_URL`` is the single switch for both the
app and the migrations. ``target_metadata`` is the union of the auth models
(``app.services.dbmodel``) and the check-persistence model
(``app.services.report_model``), all of which share one ``Base``.

Python 3.9 compatible: ``from __future__ import annotations`` and no PEP 604
``X | None`` unions.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the repo root importable so ``from app...`` resolves when alembic is run
# from the command line (alembic only puts the script dir on sys.path).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

config = context.config

# Interpret the config file for Python logging (no-op if the file is absent).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Register all models on the shared Base's metadata. Importing the modules is
# enough; both define their tables on app.services.database.Base.
from app.services import dbmodel, report_model  # noqa: F401,E402
from app.services.database import Base, DATABASE_URL  # noqa: E402

target_metadata = Base.metadata

# Point Alembic at the app engine URL (overrides the blank value in alembic.ini).
config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations without a live DBAPI connection (emit SQL)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection (the normal path)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
