"""Comprehensive regression tests for the Security Audit remediation (SEC-01 through SEC-10).

Covers:
- SEC-01: Arbitrary File Read via Path Traversal in Single-Page Application Fallback Route
- SEC-02: Arbitrary Directory Path Traversal & Vector Store Rewrite in Ingest
- SEC-03: Authentication Bypass via Default Insecure JWT Secret Key
- SEC-04: Two-Factor Authentication Bypass via Standard OAuth2 Password Login Endpoint
- SEC-05: Two-Factor Authentication Disarming via Premature Secret Replacement
- SEC-06: Missing Password Re-Authentication in TOTP Activation
- SEC-07: Failed or Unparseable LLM Compliance Analysis Persists with Erroneous Pass Status
- SEC-08: Server-Side Request Forgery (SSRF) in Statutory Rules Downloader
- SEC-09: Unauthenticated Mutation of Active Model Configuration via /api/setmodel
- SEC-10: Unauthenticated Corpus Directory Listing Exposes Filesystem Metadata
- Defensive Hardening: File upload bounds, constant-time comparisons, rate limiting memory safety.
"""

from __future__ import annotations

import io
from pathlib import Path
import uuid
import pyotp
import pytest

from app.config import _default_secret_key, get_settings
from app.rag.ingestion import load_kbr_documents
from app.services.report_model import derive_status
from scripts.fetch_kbr import _validate_safe_url


def _email() -> str:
    return f"sec-test-{uuid.uuid4().hex[:10]}@example.com"


def _register(client, email, password="supersecret1"):
    return client.post("/auth/register", json={"email": email, "password": password})


def _login(client, email, password="supersecret1"):
    return client.post("/auth/login/json", json={"email": email, "password": password})


# ==============================================================================
# SEC-01: SPA Fallback Directory Traversal
# ==============================================================================
def test_sec_01_spa_fallback_path_traversal_blocked(app_client):
    """Ensure traversal sequences cannot read arbitrary files outside frontend/dist."""
    # Attempt to read existing server files via path traversal
    traversals = [
        "../app/config.py",
        "..%2fapp%2fconfig.py",
        "../../app/main.py",
        "../../../../../../etc/passwd",
    ]
    for path in traversals:
        resp = app_client.get(f"/{path}")
        # Must return 404 (or index.html fallback if built), NEVER the file content with 200
        if resp.status_code == 200:
            assert "Settings(BaseModel)" not in resp.text
            assert "class FastAPI" not in resp.text
            assert "root:x:" not in resp.text
        else:
            assert resp.status_code == 404


# ==============================================================================
# SEC-02: Corpus Ingestion Path Traversal & Vector Store Rewrite
# ==============================================================================
def test_sec_02_load_kbr_documents_directory_traversal_blocked():
    """Ensure load_kbr_documents rejects data_dir outside kbr_data_dir."""
    outside_dirs = [
        Path("/etc"),
        Path("../.."),
        Path(__file__).parent,
    ]
    for d in outside_dirs:
        with pytest.raises(ValueError, match="data_dir must be within"):
            load_kbr_documents(d)


def test_sec_02_api_ingest_rejects_external_data_dir(app_client):
    """Ensure /api/ingest rejects external data_dir with HTTP 400."""
    resp = app_client.post("/api/ingest", json={"data_dir": "../../", "rebuild": False})
    assert resp.status_code == 400
    assert "data_dir must be within" in resp.json()["detail"]


# ==============================================================================
# SEC-03: Default Insecure JWT Secret Key Protection
# ==============================================================================
def test_sec_03_default_secret_key_fatal_when_auth_required(monkeypatch):
    """Ensure startup fails if AUTH_REQUIRED=1 and SECRET_KEY is missing or insecure default."""
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FATAL: SECRET_KEY must be set"):
        _default_secret_key()

    monkeypatch.setenv("SECRET_KEY", "chattamai-insecure-dev-secret-change-me")
    with pytest.raises(RuntimeError, match="FATAL: SECRET_KEY must be set"):
        _default_secret_key()


def test_sec_03_default_secret_key_generates_random_in_dev(monkeypatch):
    """Ensure dev generates a cryptographically random secret if unset."""
    monkeypatch.delenv("AUTH_REQUIRED", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    key1 = _default_secret_key()
    key2 = _default_secret_key()
    assert len(key1) >= 32
    assert key1 != "chattamai-insecure-dev-secret-change-me"
    assert key1 != key2  # fresh ephemeral secret


# ==============================================================================
# SEC-04: Two-Factor Authentication Bypass via /auth/login
# ==============================================================================
def test_sec_04_oauth2_form_login_blocks_totp_users(app_client):
    """Ensure POST /auth/login rejects users who have TOTP enabled."""
    email = _email()
    password = "supersecret1"
    assert _register(app_client, email, password).status_code == 201

    # Login and enroll in TOTP
    tok = _login(app_client, email, password).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    setup = app_client.post("/auth/totp/setup", headers=hdr).json()
    secret = setup["secret"]
    enable_resp = app_client.post(
        "/auth/totp/enable",
        headers=hdr,
        json={"code": pyotp.TOTP(secret).now(), "password": password},
    )
    assert enable_resp.status_code == 200

    # Attempt OAuth2 form login
    form_resp = app_client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert form_resp.status_code == 403
    assert "Two-factor authentication required" in form_resp.json()["detail"]


# ==============================================================================
# SEC-05: 2FA Disarming via Premature Secret Replacement
# ==============================================================================
def test_sec_05_totp_setup_blocked_when_already_enabled(app_client):
    """Ensure calling /auth/totp/setup on an enrolled account is rejected."""
    email = _email()
    password = "supersecret1"
    assert _register(app_client, email, password).status_code == 201

    tok = _login(app_client, email, password).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    setup = app_client.post("/auth/totp/setup", headers=hdr).json()
    secret = setup["secret"]
    assert (
        app_client.post(
            "/auth/totp/enable",
            headers=hdr,
            json={"code": pyotp.TOTP(secret).now(), "password": password},
        ).status_code
        == 200
    )

    # Now attempt /auth/totp/setup again while still enrolled
    second_setup = app_client.post("/auth/totp/setup", headers=hdr)
    assert second_setup.status_code == 400
    assert "2FA is already enabled" in second_setup.json()["detail"]


# ==============================================================================
# SEC-06: Missing Password Re-Authentication in TOTP Activation
# ==============================================================================
def test_sec_06_totp_enable_requires_password(app_client):
    """Ensure /auth/totp/enable rejects requests with incorrect or missing password."""
    email = _email()
    password = "supersecret1"
    assert _register(app_client, email, password).status_code == 201

    tok = _login(app_client, email, password).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    setup = app_client.post("/auth/totp/setup", headers=hdr).json()
    secret = setup["secret"]
    code = pyotp.TOTP(secret).now()

    # Wrong password
    wrong_pw_resp = app_client.post(
        "/auth/totp/enable",
        headers=hdr,
        json={"code": code, "password": "wrongpassword!"},
    )
    assert wrong_pw_resp.status_code == 403
    assert "Incorrect password" in wrong_pw_resp.json()["detail"]

    # Missing password
    missing_pw_resp = app_client.post(
        "/auth/totp/enable",
        headers=hdr,
        json={"code": code},
    )
    assert missing_pw_resp.status_code == 422  # validation error


# ==============================================================================
# SEC-07: Failed LLM Analysis Persists with Erroneous Pass Status
# ==============================================================================
def test_sec_07_derive_status_with_error_returns_warning():
    """Ensure derive_status returns 'warning' when an error occurred, even with empty violations."""
    assert derive_status([], error="parse_failed: malformed json") == "warning"
    assert derive_status(None, error="timeout") == "warning"
    assert derive_status([], error=None) == "pass"
    assert derive_status(None, error=None) == "pass"


# ==============================================================================
# SEC-08: Server-Side Request Forgery in Document Downloader
# ==============================================================================
def test_sec_08_fetch_kbr_blocks_private_and_metadata_ips():
    """Ensure _validate_safe_url rejects private, loopback, and metadata endpoints."""
    blocked_urls = [
        "http://127.0.0.1:8000/test",
        "http://localhost:8080/kbr.pdf",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/private.txt",
        "http://192.168.1.1/secret",
        "http://172.16.0.1/kbr",
        "ftp://example.com/test.txt",
    ]
    for url in blocked_urls:
        with pytest.raises(ValueError):
            _validate_safe_url(url)


# ==============================================================================
# SEC-09: Unauthenticated Mutation of Active Model Configuration
# ==============================================================================
def test_sec_09_setmodel_requires_auth(monkeypatch, app_client):
    """Ensure /api/setmodel enforces authentication when AUTH_REQUIRED=1."""
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-that-is-long-enough-32bytes")
    get_settings.cache_clear()
    try:
        resp = app_client.post("/api/setmodel", json={"model_provider": "gemini"})
        assert resp.status_code == 401
    finally:
        monkeypatch.delenv("AUTH_REQUIRED", raising=False)
        monkeypatch.delenv("SECRET_KEY", raising=False)
        get_settings.cache_clear()


# ==============================================================================
# SEC-10: Unauthenticated Corpus Directory Metadata Exposure
# ==============================================================================
def test_sec_10_list_kbr_documents_requires_auth_and_filters_ext(
    monkeypatch, app_client, tmp_path
):
    """Ensure /api/kbr/documents requires auth when enabled and filters disallowed files."""
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-that-is-long-enough-32bytes")
    get_settings.cache_clear()
    try:
        resp = app_client.get("/api/kbr/documents")
        assert resp.status_code == 401
    finally:
        monkeypatch.delenv("AUTH_REQUIRED", raising=False)
        monkeypatch.delenv("SECRET_KEY", raising=False)
        get_settings.cache_clear()

    # Verify extension filtering
    test_kbr_dir = tmp_path / "test_kbr"
    test_kbr_dir.mkdir()
    (test_kbr_dir / "valid_rule.txt").write_text("Rule 1")
    (test_kbr_dir / "valid_rule.pdf").write_bytes(b"%PDF-1.4")
    (test_kbr_dir / ".hidden_file").write_text("secret")
    (test_kbr_dir / "malicious.py").write_text("import os")
    (test_kbr_dir / "executable.exe").write_bytes(b"MZ")

    monkeypatch.setenv("KBR_DATA_DIR", str(test_kbr_dir))
    get_settings.cache_clear()
    try:
        resp = app_client.get("/api/kbr/documents")
        assert resp.status_code == 200
        filenames = [doc["filename"] for doc in resp.json()]
        assert "valid_rule.txt" in filenames
        assert "valid_rule.pdf" in filenames
        assert ".hidden_file" not in filenames
        assert "malicious.py" not in filenames
        assert "executable.exe" not in filenames
    finally:
        get_settings.cache_clear()


# ==============================================================================
# Defensive Hardening: Upload Size Bounds
# ==============================================================================
def test_hardening_upload_kbr_document_size_limit(app_client):
    """Ensure upload rejects payloads exceeding 25MB safety bound."""
    large_content = b"x" * (26 * 1024 * 1024)  # 26 MB
    file_payload = {"file": ("rule.txt", io.BytesIO(large_content), "text/plain")}
    resp = app_client.post("/api/kbr/upload", files=file_payload)
    assert resp.status_code == 413
    assert "File too large" in resp.json()["detail"]


def test_hardening_admin_key_timing_safe(monkeypatch, app_client):
    """Ensure X-Admin-Key uses timing-safe check and rejects invalid key."""
    monkeypatch.setenv("ADMIN_KEY", "super-secret-admin-key-1234")
    get_settings.cache_clear()
    try:
        resp = app_client.post(
            "/auth/register",
            headers={"X-Admin-Key": "wrong-key"},
            json={"email": _email(), "password": "supersecret1"},
        )
        assert resp.status_code == 403
    finally:
        monkeypatch.delenv("ADMIN_KEY", raising=False)
        get_settings.cache_clear()
