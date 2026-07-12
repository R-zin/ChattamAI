from database import Base
from datetime import datetime,timedelta
from sqlalchemy import Integer, Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import os
import hashlib

TIME_OUT = int(os.getenv('TIME_OUT'))

def expiry_time():
    return datetime.now() + timedelta(seconds=TIME_OUT)
def hash_password(password):
    return hashlib.sha512(password.encode('utf-8')).hexdigest()


class User(Base):
    __tablename__ = "user"
    user_id = Column(String,primary_key=True)
    email = Column(String)
    password = Column(String,default=hash_password)
    created_at = Column(DateTime)
    sessions = relationship("userSession", back_populates="user",
                            cascade="all, delete, delete-orphan")

class UserSession(Base):
    __tablename__ = "userSession"
    session_id = Column(String,primary_key=True)
    user_id = Column(String,ForeignKey("user.user_id"),nullable=False)
    expires_at = Column(DateTime,default=expiry_time)
    user = relationship("User",back_populates="sessions")




