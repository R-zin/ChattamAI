"""Database models + password hashing + JWT helpers for the auth layer.

Passwords are hashed with bcrypt (via passlib). This replaces the previous
unsalted SHA-512 (``hashlib.sha512``) — see the migration note on
:func:`hash_password`. JWTs are signed with ``python-jose``.

Python 3.9 compatible: ``from __future__ import annotations`` and no PEP 604
``X | None`` unions.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.services.database import Base

# --- Auth settings (source: app.config.Settings; overridden here only as a fallback) ---
#   Settings.secret_key            (SECRET_KEY)      — JWT signing key. MUST be
#                                                     overridden in production.
#   Settings.auth_algorithm        (AUTH_ALGORITHM)  — JWT algorithm (HS256).
#   Settings.session_timeout_seconds (TIME_OUT)      — token TTL (3600).
#   Settings.auth_required         (AUTH_REQUIRED)   — enforce auth on protected routes.
#   Settings.admin_key             (ADMIN_KEY)       — admin header to gate /auth/register.
_INSECURE_DEFAULT_SECRET = "chattamai-insecure-dev-secret-change-me"


def _auth_secret() -> str:
    try:
        from app.config import get_settings

        return get_settings().secret_key
    except Exception:
        return _INSECURE_DEFAULT_SECRET


def _auth_algorithm() -> str:
    try:
        from app.config import get_settings

        return get_settings().auth_algorithm
    except Exception:
        return "HS256"


def _token_ttl_seconds() -> int:
    try:
        from app.config import get_settings

        return int(get_settings().session_timeout_seconds)
    except Exception:
        return 3600


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def expiry_time() -> datetime:
    return datetime.utcnow() + timedelta(seconds=_token_ttl_seconds())


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt.

    Migration note: this previously used unsalted ``hashlib.sha512``. Any hashes
    stored by the old scheme will NOT verify against :func:`verify_password` and
    those users must re-register (or have their passwords reset).
    """
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if ``plain_password`` matches the bcrypt ``hashed_password``."""
    try:
        return _pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        # Malformed/foreign hash (e.g. a legacy SHA-512 value) -> never matches.
        return False


def create_access_token(
    user_id: str,
    email: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT carrying the user id + email, expiring after the TTL."""
    expire = datetime.utcnow() + (
        expires_delta
        if expires_delta is not None
        else timedelta(seconds=_token_ttl_seconds())
    )
    claims: Dict[str, Any] = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(claims, _auth_secret(), algorithm=_auth_algorithm())


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode + validate a JWT. Raises ``jose.JWTError`` if invalid/expired."""
    return jwt.decode(token, _auth_secret(), algorithms=[_auth_algorithm()])


def new_id() -> str:
    """Generate a primary-key value for User/UserSession rows."""
    return uuid.uuid4().hex


# --- TOTP / 2FA helpers -----------------------------------------------------


def _otp_challenge_ttl_seconds() -> int:
    try:
        from app.config import get_settings

        return int(get_settings().otp_challenge_ttl_seconds)
    except Exception:
        return 300


def _recovery_count() -> int:
    try:
        from app.config import get_settings

        return int(get_settings().totp_recovery_count)
    except Exception:
        return 8


def create_otp_challenge_token(
    user_id: str,
    email: str,
    setup_required: bool = False,
) -> str:
    """Short-lived, single-purpose token issued after a correct password for a
    user who must complete TOTP. NOT an access token: the ``purpose`` claim is
    what ``get_current_user`` uses to reject it as a session token."""
    expire = datetime.utcnow() + timedelta(seconds=_otp_challenge_ttl_seconds())
    claims: Dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "purpose": "totp",
        "setup": setup_required,
    }
    return jwt.encode(claims, _auth_secret(), algorithm=_auth_algorithm())


def decode_otp_challenge_token(token: str) -> Dict[str, Any]:
    """Decode a challenge token and assert it is a TOTP challenge (not an
    access token). Raises ``jose.JWTError`` otherwise."""
    payload = jwt.decode(token, _auth_secret(), algorithms=[_auth_algorithm()])
    if payload.get("purpose") != "totp":
        raise JWTError("not a totp challenge token")
    return payload


def hash_recovery_code(code: str) -> str:
    """Hash a recovery code for at-rest storage. A plain sha256 is correct here
    (unlike passwords): recovery codes are single-use, high-entropy, machine-
    generated secrets, so a slow salted KDF buys nothing and bcrypt's 72-byte
    quirks (see requirements.txt) are needless risk."""
    return hashlib.sha256(code.strip().lower().encode("utf-8")).hexdigest()


def generate_recovery_codes(count: Optional[int] = None) -> List[str]:
    """Generate ``count`` plaintext recovery codes (10 hex chars each). Shown to
    the user ONCE at enable-time; only their hashes are stored."""
    n = _recovery_count() if count is None else int(count)
    return [secrets.token_hex(5) for _ in range(n)]


class User(Base):
    __tablename__ = "user"
    user_id = Column(String, primary_key=True, default=new_id)
    email = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # 2FA (TOTP). The base32 secret is set at setup-time; ``totp_enabled`` flips
    # True only after the user proves they control the secret (first valid code).
    totp_secret = Column(String, nullable=True)
    totp_enabled = Column(Boolean, nullable=False, default=False)
    sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete, delete-orphan"
    )
    recovery_codes = relationship(
        "RecoveryCode", back_populates="user", cascade="all, delete, delete-orphan"
    )


class RecoveryCode(Base):
    __tablename__ = "recovery_code"
    code_id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("user.user_id"), nullable=False, index=True)
    code_hash = Column(String, nullable=False)  # sha256 hex of the plaintext code
    used_at = Column(DateTime, nullable=True)  # NULL = still available
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    user = relationship("User", back_populates="recovery_codes")


class UserSession(Base):
    __tablename__ = "userSession"
    session_id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("user.user_id"), nullable=False)
    expires_at = Column(DateTime, default=expiry_time)
    user = relationship("User", back_populates="sessions")


__all__ = [
    "User",
    "UserSession",
    "RecoveryCode",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "create_otp_challenge_token",
    "decode_otp_challenge_token",
    "hash_recovery_code",
    "generate_recovery_codes",
    "new_id",
    "expiry_time",
    "JWTError",
]
