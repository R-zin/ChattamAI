"""Database models + password hashing + JWT helpers for the auth layer.

Passwords are hashed with bcrypt (via passlib). This replaces the previous
unsalted SHA-512 (``hashlib.sha512``) — see the migration note on
:func:`hash_password`. JWTs are signed with ``python-jose``.

Python 3.9 compatible: ``from __future__ import annotations`` and no PEP 604
``X | None`` unions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import Column, DateTime, ForeignKey, String
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


class User(Base):
    __tablename__ = "user"
    user_id = Column(String, primary_key=True, default=new_id)
    email = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete, delete-orphan"
    )


class UserSession(Base):
    __tablename__ = "userSession"
    session_id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("user.user_id"), nullable=False)
    expires_at = Column(DateTime, default=expiry_time)
    user = relationship("User", back_populates="sessions")


__all__ = [
    "User",
    "UserSession",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "new_id",
    "expiry_time",
    "JWTError",
]
