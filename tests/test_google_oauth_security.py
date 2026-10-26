"""Tests for Google OAuth 2.0 integration and security hardening controls."""

from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.database import SessionLocal
from app.services.database_init import init_db
from app.services.dbmodel import (
    User,
    create_oauth_state_token,
    decode_oauth_state_token,
    hash_password,
    new_id,
)
from app.services.totp import new_totp_secret


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_security_headers_present_on_responses(client):
    """Verify that defense-in-depth security headers are attached to API responses."""
    resp = client.get("/")
    assert resp.status_code == 200
    headers = resp.headers

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert "https://accounts.google.com" in headers["Content-Security-Policy"]


def test_google_auth_url_generation(client):
    """Verify GET /auth/google/url returns a valid Google OAuth URL with a signed CSRF state."""
    resp = client.get("/auth/google/url?redirect_uri=http://localhost:5173/login")
    assert resp.status_code == 200
    data = resp.json()

    assert "url" in data
    assert "accounts.google.com/o/oauth2/v2/auth" in data["url"]
    assert "state" in data
    assert data["state"] in data["url"]

    # Verify state token payload is valid and has google_oauth_state purpose
    decoded = decode_oauth_state_token(data["state"])
    assert decoded["purpose"] == "google_oauth_state"
    assert decoded["redirect_uri"] == "http://localhost:5173/login"


def test_google_callback_rejects_invalid_or_tampered_state(client):
    """Verify POST /auth/google/callback fails when state token is forged or invalid."""
    resp = client.post(
        "/auth/google/callback",
        json={
            "code": "mock-google-code-test",
            "state": "forged-or-invalid-state-token",
            "redirect_uri": "http://localhost:5173/login",
        },
    )
    assert resp.status_code == 400
    assert "Invalid or expired OAuth state token" in resp.json()["detail"]


def test_google_callback_provisions_new_user_and_logs_in(client, db):
    """Verify valid Google code provisions a new user and issues a signed JWT."""
    test_email = "new-architect@kerala-lsgd.gov.in"
    # Ensure test user doesn't already exist
    db.query(User).filter(User.email == test_email).delete()
    db.commit()

    state = create_oauth_state_token("http://localhost:5173/login")
    resp = client.post(
        "/auth/google/callback",
        json={
            "code": f"mock-google-code-{test_email}",
            "state": state,
            "redirect_uri": "http://localhost:5173/login",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0

    # Verify user exists in DB with auth_provider='google'
    created = db.query(User).filter(User.email == test_email).first()
    assert created is not None
    assert created.auth_provider == "google"
    assert created.google_sub is not None


def test_google_callback_links_existing_user(client, db):
    """Verify Google sign-in links an existing local user with matching verified email."""
    test_email = "existing-user@chattamai.com"
    existing = db.query(User).filter(User.email == test_email).first()
    if not existing:
        existing = User(
            user_id=new_id(),
            email=test_email,
            password=hash_password("ExistingPassword123!"),
            auth_provider="local",
        )
        db.add(existing)
        db.commit()

    state = create_oauth_state_token("http://localhost:5173/login")
    resp = client.post(
        "/auth/google/callback",
        json={
            "code": f"mock-google-code-{test_email}",
            "state": state,
            "redirect_uri": "http://localhost:5173/login",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data

    # Verify user's google_sub is linked
    user_in_db = db.query(User).filter(User.email == test_email).first()
    assert user_in_db.google_sub is not None


def test_google_callback_enforces_totp_when_enabled(client, db):
    """Verify that a user who enabled 2FA still must pass TOTP after Google login."""
    test_email = "2fa-architect@chattamai.com"
    user = db.query(User).filter(User.email == test_email).first()
    if not user:
        user = User(
            user_id=new_id(),
            email=test_email,
            password=hash_password("Pass123!"),
            totp_secret=new_totp_secret(),
            totp_enabled=True,
            auth_provider="google",
        )
        db.add(user)
        db.commit()
    else:
        user.totp_enabled = True
        user.totp_secret = new_totp_secret()
        db.commit()

    state = create_oauth_state_token("http://localhost:5173/login")
    resp = client.post(
        "/auth/google/callback",
        json={
            "code": f"mock-google-code-{test_email}",
            "state": state,
            "redirect_uri": "http://localhost:5173/login",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("otp_required") is True
    assert "otp_token" in data
    assert data["token_type"] == "totp-challenge"


def test_google_token_verify_endpoint(client, db):
    """Verify POST /auth/google/token verifies an ID token and logs in."""
    test_email = "onetap-user@gmail.com"
    resp = client.post(
        "/auth/google/token",
        json={"credential": f"mock-google-token-{test_email}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_magic_bytes_pdf_validation(client):
    """Verify uploading a fake PDF without %PDF- magic bytes is rejected."""
    fake_pdf = io.BytesIO(b"This is NOT a valid PDF header, it is raw binary text.")
    resp = client.post(
        "/api/v2/check/pdf",
        files={"file": ("malicious_plan.pdf", fake_pdf, "application/pdf")},
    )
    assert resp.status_code == 400
    assert "missing %PDF magic header" in resp.json()["detail"]
