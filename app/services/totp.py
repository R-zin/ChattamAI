"""TOTP (2FA) primitives.

This module is the single import site for ``pyotp`` and ``qrcode`` so the rest
of the app never touches those libraries directly. The QR code is rendered to a
PNG data-URI here (not the frontend) so the SPA needs no QR npm dependency; PNG
is chosen over SVG to avoid any SVG-injection surface. Recovery-code storage /
hashing lives in :mod:`app.services.dbmodel`.

Python 3.9 compatible (no PEP 604 unions).
"""

from __future__ import annotations

import base64
import io

import pyotp
import qrcode


def new_totp_secret() -> str:
    """Generate a new base32 TOTP secret."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str, issuer: str) -> str:
    """Build the ``otpauth://`` URI scanned by authenticator apps."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """Verify a 6-digit TOTP code against ``secret``.

    ``valid_window=1`` accepts the previous/current/next 30-second step to
    tolerate modest clock drift between client and server."""
    if not secret:
        return False
    try:
        return bool(pyotp.TOTP(secret).verify(code, valid_window=window))
    except Exception:
        # A malformed code/secret (wrong alphabet, length) must never match.
        return False


def qr_png_data_uri(otpauth_uri: str) -> str:
    """Render the provisioning URI to a base64 PNG data-URI."""
    img = qrcode.make(otpauth_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return "data:image/png;base64," + b64


__all__ = [
    "new_totp_secret",
    "provisioning_uri",
    "verify_totp",
    "qr_png_data_uri",
]
