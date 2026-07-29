"""Auth routes.

⚠️  NOT WIRED IN: ``app/main.py`` only mounts ``routes.rag``. This router is
scaffolding for a future user/session layer (see DEVELOPMENT.md §7) and is kept
importable so editing it never breaks the app. Finishing + mounting it is
deliberately out of scope until auth is actually wanted.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.services.database import SessionLocal
from app.services.dbmodel import User, hash_password

auth_router = APIRouter(prefix="/auth", tags=["auth"])

ADMIN_KEY = os.getenv("ADMIN_KEY")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_admin(admin_key: str) -> bool:
    if ADMIN_KEY and admin_key == ADMIN_KEY:
        return True
    raise HTTPException(status_code=401, detail="Admin key is invalid")


@auth_router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Authenticate a user. Not yet implemented (see module docstring)."""
    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or user.password != hash_password(form_data.password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    raise HTTPException(status_code=501, detail="Login not implemented yet")
