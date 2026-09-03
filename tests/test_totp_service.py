"""Unit tests for the TOTP (2FA) primitives in ``app.services.totp``.

These exercise the pure service layer (secret generation, provisioning URI,
code verification, QR rendering) directly — no HTTP, no DB, no network. Real
codes are minted with :func:`pyotp.TOTP(secret).now()` so no clock-freezing is
required.
"""

from __future__ import annotations

import base64

import pyotp

from app.services.totp import (
    new_totp_secret,
    provisioning_uri,
    qr_png_data_uri,
    verify_totp,
)


def test_new_totp_secret_is_valid_base32():
    secret = new_totp_secret()
    # base32 alphabet only, and pyotp can consume it.
    assert isinstance(secret, str) and secret
    pyotp.TOTP(secret).now()  # must not raise


def test_new_totp_secret_is_unique():
    assert new_totp_secret() != new_totp_secret()


def test_provisioning_uri_contains_email_and_issuer():
    uri = provisioning_uri("JBSWY3DPEHPK3PXP", "user@example.com", "ChattamAI")
    assert uri.startswith("otpauth://totp/")
    assert "user@example.com" in uri
    assert "ChattamAI" in uri
    assert "secret=JBSWY3DPEHPK3PXP" in uri


def test_verify_totp_accepts_current_code():
    secret = new_totp_secret()
    code = pyotp.TOTP(secret).now()
    assert verify_totp(secret, code) is True


def test_verify_totp_rejects_wrong_code():
    secret = new_totp_secret()
    assert verify_totp(secret, "000000") is False


def test_verify_totp_empty_secret_never_matches():
    assert verify_totp("", "123456") is False


def test_verify_totp_malformed_inputs_never_match():
    secret = new_totp_secret()
    # A malformed code (non-numeric / wrong length) must not raise and must fail.
    assert verify_totp(secret, "not-a-code") is False
    assert verify_totp(secret, "") is False
    # A malformed secret must not raise and must fail.
    assert verify_totp("!!!not-base32!!!", "123456") is False


def test_qr_png_data_uri_is_valid_png():
    uri = provisioning_uri(new_totp_secret(), "u@example.com", "ChattamAI")
    data_uri = qr_png_data_uri(uri)
    assert data_uri.startswith("data:image/png;base64,")
    payload = data_uri.split(",", 1)[1]
    raw = base64.b64decode(payload)
    # PNG magic bytes.
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(raw) > 100  # a real rendered image, not an empty buffer
