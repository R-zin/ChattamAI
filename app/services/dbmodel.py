from database import Base
from datetime import datetime,timedelta
from sqlalchemy import Integer, Column, String, DateTime, ForeignKey
import os
import hashlib

TIME_OUT = int(os.getenv('TIME_OUT'))

def expiry_time():
    return datetime.now() + timedelta(seconds=TIME_OUT)

class User(Base):
    __tablename__ = "user"
    session_id = Column(String)
    user_id = Column(String,primary_key=True)
    expires_at = Column(DateTime,default=expiry_time)
