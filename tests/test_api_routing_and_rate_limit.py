"""Unknown API paths return JSON 404; rate limiting can't be dodged via XFF."""

from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.main import client_ip_for


def req(xff=None, peer="10.0.0.9"):
    headers = {"x-forwarded-for": xff} if xff is not None else {}
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


# -- client_ip_for -----------------------------------------------------------
def test_ignores_xff_without_trusted_proxies():
    assert client_ip_for(req("1.2.3.4"), 0) == "10.0.0.9"


def test_takes_entry_written_by_the_trusted_proxy():
    # Attacker sent "6.6.6.6"; our proxy appended the real peer it saw.
    assert client_ip_for(req("6.6.6.6, 203.0.113.7"), 1) == "203.0.113.7"


def test_two_trusted_hops():
    xff = "6.6.6.6, 203.0.113.7, 172.16.0.5"
    assert client_ip_for(req(xff), 2) == "203.0.113.7"


def test_falls_back_to_peer_when_header_missing_or_short():
    assert client_ip_for(req(None), 1) == "10.0.0.9"
    assert client_ip_for(req("203.0.113.7"), 2) == "10.0.0.9"


# -- JSON 404 for unknown API paths ------------------------------------------
@pytest.mark.parametrize(
    "path", ["/api/nope", "/api/v2/nope", "/auth/nope", "/api", "/api/"]
)
def test_unknown_api_paths_are_json_404(app_client, path):
    resp = app_client.get(path, headers={"accept": "text/html"})
    assert resp.status_code == 404, path
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"detail": "Not found"}


def test_known_api_routes_still_work(app_client):
    assert app_client.get("/api/health").status_code == 200


def test_non_api_paths_still_fall_back_to_spa(app_client, tmp_path, monkeypatch):
    import app.main as main

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>spa</html>")
    monkeypatch.setattr(main, "_DIST_DIR", dist)
    resp = app_client.get("/reports")
    assert resp.status_code == 200
    assert "spa" in resp.text
    # A path that merely starts with "api" is not an API path.
    assert app_client.get("/apiary").status_code == 200


# -- rate limiter end to end -------------------------------------------------
def test_spoofed_xff_cannot_evade_rate_limit(app_client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)
    monkeypatch.setattr(settings, "trusted_proxy_count", 0)
    statuses = [
        app_client.get(
            "/api/v2/rules/tables", headers={"x-forwarded-for": f"9.9.9.{i}"}
        )
        for i in range(5)
    ]
    assert [r.status_code for r in statuses][-1] == 429


def test_distinct_clients_behind_trusted_proxy_get_separate_buckets(
    app_client, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)

    def hit(real_ip):
        return app_client.get(
            "/api/v2/rules/tables", headers={"x-forwarded-for": f"6.6.6.6, {real_ip}"}
        ).status_code

    assert [hit("203.0.113.1") for _ in range(3)][-1] == 429
    assert hit("203.0.113.2") != 429
