import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Default to a local SQLite file so this module imports cleanly without any
# configuration. Set DATABASE_URL to point at a real database.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./chattamai.db")

engine = create_engine(
    DATABASE_URL,
    # Required for SQLite when sharing the connection across threads (FastAPI).
    connect_args=(
        {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    ),
)

SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)

Base = declarative_base()
