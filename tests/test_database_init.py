"""database_init: quoted ALTERs for legacy DBs; fallbacks skipped after Alembic."""

import pytest
from sqlalchemy import create_engine, inspect, text

from app.services import database_init


@pytest.fixture
def legacy_engine(tmp_path, monkeypatch):
    """A SQLite DB whose user/report tables predate the later columns."""
    eng = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with eng.begin() as conn:
        conn.execute(
            text('CREATE TABLE "user" (id VARCHAR PRIMARY KEY, email VARCHAR)')
        )
        conn.execute(text("CREATE TABLE report (report_id INTEGER PRIMARY KEY)"))
    monkeypatch.setattr(database_init, "engine", eng)
    return eng


def test_legacy_user_table_gets_missing_columns(legacy_engine):
    database_init._ensure_user_totp_columns()
    cols = {c["name"] for c in inspect(legacy_engine).get_columns("user")}
    assert {"totp_secret", "totp_enabled", "auth_provider", "google_sub"} <= cols


def test_legacy_report_table_gets_verification_column(legacy_engine):
    database_init._ensure_report_verification_column()
    cols = {c["name"] for c in inspect(legacy_engine).get_columns("report")}
    assert "verification" in cols


def test_user_table_name_is_quoted_in_every_alter():
    import inspect as pyinspect

    src = pyinspect.getsource(database_init._ensure_user_totp_columns)
    assert "ALTER TABLE user " not in src
    assert src.count('ALTER TABLE "user"') == 4


@pytest.mark.parametrize("alembic_ok", [True, False])
def test_column_fallbacks_only_run_when_alembic_failed(monkeypatch, alembic_ok):
    calls = []
    monkeypatch.setattr(database_init, "_run_alembic_upgrade", lambda: alembic_ok)
    monkeypatch.setattr(
        database_init.Base.metadata,
        "create_all",
        lambda **kw: calls.append("create_all"),
    )
    monkeypatch.setattr(
        database_init, "_ensure_user_totp_columns", lambda: calls.append("user")
    )
    monkeypatch.setattr(
        database_init,
        "_ensure_report_verification_column",
        lambda: calls.append("report"),
    )
    database_init.init_db()
    assert calls == ([] if alembic_ok else ["create_all", "user", "report"])
