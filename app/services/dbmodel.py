"""Database models + password hashing + JWT helpers for the auth layer.

Passwords are hashed with bcrypt (via passlib). This replaces the previous
unsalted SHA-512 (``hashlib.sha512``) — see the migration note on
:func:`hash_password`. JWTs are signed with ``python-jose``.

Python 3.9 compatible: ``from __future__ import annotations`` and no PEP 604
``X | None`` unions.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.services.database import Base

# --- Auth settings (read from env with safe defaults) -------------------------
# NOTE for the coordinator: these are intentionally read via os.getenv here so
# auth works without touching app/config.py (which is out of scope). They should
# be promoted into app.config.Settings later:
#   SECRET_KEY            — JWT signing key. MUST be overridden in production.
#   AUTH_ALGORITHM        — JWT algorithm (default HS256).
#   TIME_OUT              — access-token / session TTL in seconds (default 3600).
#   AUTH_REQUIRED         — "true" to enforce auth on protected routes (default off).
#   ADMIN_KEY             — optional admin header to gate /auth/register.
SECRET_KEY = os.getenv("SECRET_KEY", "chattamai-insecure-dev-secret-change-me")
AUTH_ALGORITHM = os.getenv("AUTH_ALGORITHM", "HS256")

# Session/token lifetime in seconds; overridable via TIME_OUT. Read lazily so the
# module imports even if the variable is malformed, and has a sane default.
DEFAULT_TIME_OUT = int(os.getenv("TIME_OUT", "3600"))

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def expiry_time() -> datetime:
    return datetime.utcnow() + timedelta(seconds=DEFAULT_TIME_OUT)


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
        else timedelta(seconds=DEFAULT_TIME_OUT)
    )
    claims: Dict[str, Any] = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(claims, SECRET_KEY, algorithm=AUTH_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode + validate a JWT. Raises ``jose.JWTError`` if invalid/expired."""
    return jwt.decode(token, SECRET_KEY, algorithms=[AUTH_ALGORITHM])


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
    "SECRET_KEY",
    "AUTH_ALGORITHM",
    "DEFAULT_TIME_OUT",
]
