"""Offline tests for the TOTP (2FA) auth flow.

Reuses the ``app_client`` fixture from ``conftest.py`` (temp-sqlite DB, RAG
fakes, no network). Each test registers a FRESH user with a unique email so the
suite is order-independent and re-runnable against the shared temp DB. Real
codes are minted with :func:`pyotp.TOTP(secret).now()` from the secret the setup
endpoint returns, so no clock-freezing is needed.

Covers the plan's A.1.7 matrix: baseline login unchanged, setup/enable/disable,
the challenge-token-as-session gate, verify good/bad code, single-use recovery,
and the TOTP_REQUIRED forced-enroll toggle.
"""

from __future__ import annotations

import uuid

import pyotp
import pytest

from app.config import get_settings


def _email() -> str:
    return f"u-{uuid.uuid4().hex[:12]}@example.com"


def _register(client, email, password="supersecret1"):
    # If the user already exists (conftest's temp DB persists between runs),
    # wipe the stale row and any 2FA state first so this test always starts
    # from a clean slate regardless of previous runs.
    from app.routes.auth import get_db, _get_user_by_email
    from app.services.dbmodel import RecoveryCode

    db = next(get_db())
    try:
        existing = _get_user_by_email(db, email)
        if existing is not None:
            db.query(RecoveryCode).filter(
                RecoveryCode.user_id == existing.user_id
            ).delete(synchronize_session=False)
            db.delete(existing)
            db.commit()
    finally:
        db.close()
    return client.post("/auth/register", json={"email": email, "password": password})


def _login(client, email, password="supersecret1"):
    return client.post("/auth/login/json", json={"email": email, "password": password})


def _enroll(client, email, password="supersecret1"):
    """Register, enable TOTP, and return (email, access_token_qr_secret, codes)."""
    assert _register(client, email, password).status_code == 201
    # password -> challenge (TOTP_REQUIRED off by default, so a fresh user is NOT
    # forced; we enable via a pre-login access token).
    login = _login(client, email, password).json()
    assert "access_token" in login  # unenrolled + toggle off => straight token
    hdr = {"Authorization": f"Bearer {login['access_token']}"}
    setup = client.post("/auth/totp/setup", headers=hdr).json()
    secret = setup["secret"]
    enable = client.post(
        "/auth/totp/enable", headers=hdr, json={"code": pyotp.TOTP(secret).now()}
    )
    assert enable.status_code == 200, enable.text
    return email, secret, enable.json()["recovery_codes"]


@pytest.fixture
def totp_required(app_client):
    """Force TOTP_REQUIRED on for the duration of a test, then restore.

    Depends on ``app_client`` so the env var is set BEFORE the app (and its
    ``get_settings()`` @lru_cache) is first touched during the client's boot;
    otherwise the cached settings would already hold ``totp_required=False``.
    """
    import os

    old = os.environ.get("TOTP_REQUIRED")
    os.environ["TOTP_REQUIRED"] = "1"
    get_settings.cache_clear()
    yield app_client
    if old is None:
        os.environ.pop("TOTP_REQUIRED", None)
    else:
        os.environ["TOTP_REQUIRED"] = old
    get_settings.cache_clear()


def test_login_without_totp_is_unchanged(app_client):
    email = _email()
    assert _register(app_client, email).status_code == 201
    res = _login(app_client, email)
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body and "otp_required" not in body


def test_setup_returns_qr_and_secret_not_yet_enabled(app_client):
    email = _email()
    _register(app_client, email)
    tok = _login(app_client, email).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    setup = app_client.post("/auth/totp/setup", headers=hdr)
    assert setup.status_code == 200
    body = setup.json()
    assert body["qr_png_data_uri"].startswith("data:image/png;base64,")
    assert body["secret"] and body["otpauth_uri"].startswith("otpauth://")
    # Not enabled until a first valid code confirms.
    status = app_client.get("/auth/totp/status", headers=hdr).json()
    assert status["totp_enabled"] is False


def test_enable_rejects_wrong_code(app_client):
    email = _email()
    _register(app_client, email)
    tok = _login(app_client, email).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    app_client.post("/auth/totp/setup", headers=hdr)
    res = app_client.post("/auth/totp/enable", headers=hdr, json={"code": "000000"})
    assert res.status_code == 400


def test_enrolled_login_requires_totp_and_token_is_challenge(app_client):
    email, _, _ = _enroll(app_client, _email())
    # Note: _enroll registers its own email; use that same account.
    res = _login(app_client, email)
    body = res.json()
    assert body["otp_required"] is True
    assert body["token_type"] == "totp-challenge"
    assert "access_token" not in body


def test_challenge_token_is_not_an_access_token(app_client):
    email, secret, codes = _enroll(app_client, _email())
    otp_token = _login(app_client, email).json()["otp_token"]
    res = app_client.get("/auth/me", headers={"Authorization": f"Bearer {otp_token}"})
    assert res.status_code == 401


def test_verify_with_valid_code_issues_access_token(app_client):
    email, secret, _ = _enroll(app_client, _email())
    otp_token = _login(app_client, email).json()["otp_token"]
    res = app_client.post(
        "/auth/totp/verify",
        json={"otp_token": otp_token, "code": pyotp.TOTP(secret).now()},
    )
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    me = app_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["totp_enabled"] is True


def test_verify_with_wrong_code_rejected(app_client):
    email, secret, _ = _enroll(app_client, _email())
    otp_token = _login(app_client, email).json()["otp_token"]
    res = app_client.post(
        "/auth/totp/verify", json={"otp_token": otp_token, "code": "000000"}
    )
    assert res.status_code == 401


def test_recovery_code_is_single_use(app_client):
    email, secret, codes = _enroll(app_client, _email())
    assert len(codes) >= 1
    otp_token = _login(app_client, email).json()["otp_token"]
    ok = app_client.post(
        "/auth/totp/recover",
        json={"otp_token": otp_token, "recovery_code": codes[0]},
    )
    assert ok.status_code == 200, ok.text
    assert "access_token" in ok.json()
    # Same code a second time must fail.
    otp_token2 = _login(app_client, email).json()["otp_token"]
    again = app_client.post(
        "/auth/totp/recover",
        json={"otp_token": otp_token2, "recovery_code": codes[0]},
    )
    assert again.status_code == 401


def test_totp_required_forces_enrollment(totp_required):
    app_client = totp_required  # app_client is booted inside the fixture, post-env
    email = _email()
    _register(app_client, email)
    login = _login(app_client, email).json()
    assert login["otp_required"] is True
    assert login["otp_setup_required"] is True
    otp_token = login["otp_token"]

    # Can't verify before enabling (409), and the challenge token can't hit /auth/me.
    pre = app_client.post(
        "/auth/totp/verify", json={"otp_token": otp_token, "code": "000000"}
    )
    assert pre.status_code in (401, 409)
    assert (
        app_client.get(
            "/auth/me", headers={"Authorization": f"Bearer {otp_token}"}
        ).status_code
        == 401
    )

    # But the challenge token CAN reach setup/enable (forced-enroll path).
    hdr = {"Authorization": f"Bearer {otp_token}"}
    secret = app_client.post("/auth/totp/setup", headers=hdr).json()["secret"]
    enable = app_client.post(
        "/auth/totp/enable", headers=hdr, json={"code": pyotp.TOTP(secret).now()}
    )
    assert enable.status_code == 200, enable.text

    # Now verify works with a fresh login's challenge token.
    otp_token2 = _login(app_client, email).json()["otp_token"]
    ok = app_client.post(
        "/auth/totp/verify",
        json={"otp_token": otp_token2, "code": pyotp.TOTP(secret).now()},
    )
    assert ok.status_code == 200
    assert "access_token" in ok.json()


def test_totp_required_off_leaves_unenrolled_password_only(app_client):
    email = _email()
    _register(app_client, email)
    body = _login(app_client, email).json()
    assert "access_token" in body  # toggle off + not enrolled => straight token


def test_disable_requires_password_and_code_then_login_is_plain(app_client):
    email, secret, codes = _enroll(app_client, _email())
    otp_token = _login(app_client, email).json()["otp_token"]
    token = app_client.post(
        "/auth/totp/verify",
        json={"otp_token": otp_token, "code": pyotp.TOTP(secret).now()},
    ).json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}

    wrong_pw = app_client.post(
        "/auth/totp/disable",
        headers=hdr,
        json={"password": "wrongpass0", "code": pyotp.TOTP(secret).now()},
    )
    assert wrong_pw.status_code == 403
    wrong_code = app_client.post(
        "/auth/totp/disable",
        headers=hdr,
        json={"password": "supersecret1", "code": "000000"},
    )
    assert wrong_code.status_code == 400

    ok = app_client.post(
        "/auth/totp/disable",
        headers=hdr,
        json={"password": "supersecret1", "code": pyotp.TOTP(secret).now()},
    )
    assert ok.status_code == 200 and ok.json()["totp_enabled"] is False
    # After disabling, login is back to password-only.
    assert "access_token" in _login(app_client, email).json()
