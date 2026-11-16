from app.services.database import engine_kwargs, normalize_database_url


def test_postgres_schemes_use_psycopg_driver():
    for url in ("postgres://u:p@h:5432/db", "postgresql://u:p@h:5432/db"):
        assert normalize_database_url(url) == "postgresql+psycopg://u:p@h:5432/db"


def test_explicit_driver_and_sqlite_unchanged():
    assert normalize_database_url("postgresql+psycopg://u@h/db").startswith(
        "postgresql+psycopg://u@h"
    )
    assert normalize_database_url("sqlite:///./x.db") == "sqlite:///./x.db"


def test_engine_kwargs_per_backend():
    assert engine_kwargs("sqlite:///x.db") == {
        "connect_args": {"check_same_thread": False}
    }
    pg = engine_kwargs("postgresql+psycopg://u@h/db")
    assert pg["pool_pre_ping"] is True
    assert pg["connect_args"]["connect_timeout"] == 10
