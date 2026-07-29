import hashlib
import os
from datetime import datetime, timedelta

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.services.database import Base

# Session lifetime in seconds; overridable via TIME_OUT. Read lazily so the
# module imports even if the variable is malformed, and has a sane default.
DEFAULT_TIME_OUT = int(os.getenv("TIME_OUT", "3600"))


def expiry_time():
    return datetime.now() + timedelta(seconds=DEFAULT_TIME_OUT)


def hash_password(password):
    return hashlib.sha512(password.encode("utf-8")).hexdigest()


class User(Base):
    __tablename__ = "user"
    user_id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    sessions = relationship(
        "userSession", back_populates="user", cascade="all, delete, delete-orphan"
    )


class UserSession(Base):
    __tablename__ = "userSession"
    session_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("user.user_id"), nullable=False)
    expires_at = Column(DateTime, default=expiry_time)
    user = relationship("User", back_populates="sessions")
