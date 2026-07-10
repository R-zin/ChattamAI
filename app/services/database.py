from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autoflush=False,autocommit=False,bind=engine)

Base = declarative_base()