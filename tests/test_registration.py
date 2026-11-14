"""Self-service registration: policy, validation, normalisation, /auth/config."""

from __future__ import annotations

import uuid

import pytest


def _email(prefix="reg"):
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


GOOD_PW = "Sup3rSecret99"


@pytest.fixture
def admin_gated(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "the-admin-key-1234567890")
    monkeypatch.delenv("ALLOW_SELF_REGISTRATION", raising=False)


# -- policy -------------------------------------------------------------------
def test_open_when_no_admin_key(app_client, monkeypatch):
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    monkeypatch.setattr("app.routes.auth.get_settings", lambda: _NoAdmin())
    assert app_client.get("/auth/config").json()["registration_open"] is True
    r = app_client.post("/auth/register", json={"email": _email(), "password": GOOD_PW})
    assert r.status_code == 201, r.text


def test_admin_gated_by_default(app_client, admin_gated):
    assert app_client.get("/auth/config").json()["registration_open"] is False
    r = app_client.post("/auth/register", json={"email": _email(), "password": GOOD_PW})
    assert r.status_code == 403


def test_admin_key_still_works_when_gated(app_client, admin_gated):
    r = app_client.post(
        "/auth/register",
        json={"email": _email(), "password": GOOD_PW},
        headers={"X-Admin-Key": "the-admin-key-1234567890"},
    )
    assert r.status_code == 201, r.text


def test_self_registration_flag_opens_signup(app_client, admin_gated, monkeypatch):
    monkeypatch.setenv("ALLOW_SELF_REGISTRATION", "true")
    assert app_client.get("/auth/config").json()["registration_open"] is True
    email = _email()
    r = app_client.post("/auth/register", json={"email": email, "password": GOOD_PW})
    assert r.status_code == 201, r.text
    login = app_client.post(
        "/auth/login/json", json={"email": email, "password": GOOD_PW}
    )
    assert login.status_code == 200 and login.json()["access_token"]


def test_config_exposes_no_secrets(app_client):
    body = app_client.get("/auth/config").json()
    assert set(body) == {"registration_open", "totp_required", "google_enabled"}
    assert all(isinstance(v, bool) for v in body.values())


# -- validation ---------------------------------------------------------------
@pytest.fixture
def open_signup(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "k" * 24)
    monkeypatch.setenv("ALLOW_SELF_REGISTRATION", "1")


@pytest.mark.parametrize(
    "pw,why",
    [
        ("short1", "too short"),
        ("onlyletters", "no digit"),
        ("12345678", "no letter"),
        ("a1" + "x" * 80, "over 72 bytes"),
    ],
)
def test_weak_passwords_rejected(app_client, open_signup, pw, why):
    r = app_client.post("/auth/register", json={"email": _email(), "password": pw})
    assert r.status_code == 422, why


@pytest.mark.parametrize("bad", ["plainaddress", "a@b", "a b@example.com", "@x.com"])
def test_malformed_emails_rejected(app_client, open_signup, bad):
    r = app_client.post("/auth/register", json={"email": bad, "password": GOOD_PW})
    assert r.status_code == 422, bad


def test_email_is_normalised_and_unique_case_insensitively(app_client, open_signup):
    base = _email("Case")
    r1 = app_client.post(
        "/auth/register", json={"email": f"  {base.upper()}  ", "password": GOOD_PW}
    )
    assert r1.status_code == 201
    assert r1.json()["email"] == base.lower()
    r2 = app_client.post("/auth/register", json={"email": base, "password": GOOD_PW})
    assert r2.status_code == 409


def test_login_is_case_insensitive(app_client, open_signup):
    email = _email("login")
    assert (
        app_client.post(
            "/auth/register", json={"email": email, "password": GOOD_PW}
        ).status_code
        == 201
    )
    r = app_client.post(
        "/auth/login/json", json={"email": email.upper(), "password": GOOD_PW}
    )
    assert r.status_code == 200


def test_duplicate_registration_is_409(app_client, open_signup):
    email = _email("dup")
    body = {"email": email, "password": GOOD_PW}
    assert app_client.post("/auth/register", json=body).status_code == 201
    assert app_client.post("/auth/register", json=body).status_code == 409


class _NoAdmin:
    admin_key = None
    google_client_id = None
