"""Health must be honest: report why the service is not ready."""

from app.routes import rag as rag_routes


def test_health_ok_has_no_issues(app_client):
    body = app_client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["issues"] == []
    assert body["database_ready"] is True


def test_live_never_depends_on_providers(app_client):
    resp = app_client.get("/api/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}


def test_ready_200_when_everything_ready(app_client):
    assert app_client.get("/api/health/ready").status_code == 200


def test_empty_index_is_degraded_and_not_ready(app_client, monkeypatch):
    from app.main import app

    # monkeypatch restores the original property after the test.
    monkeypatch.setattr(type(app.state.rag), "index_size", property(lambda self: 0))
    resp = app_client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert any("index is empty" in i for i in body["issues"])
    assert app_client.get("/api/health/ready").status_code == 503


def test_database_failure_is_reported(app_client, monkeypatch):
    monkeypatch.setattr(rag_routes, "_database_ready", lambda: False)
    body = app_client.get("/api/health").json()
    assert body["status"] == "degraded"
    assert body["database_ready"] is False
    assert "Database is unreachable" in body["issues"]
    assert app_client.get("/api/health/ready").status_code == 503
