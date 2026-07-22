from fastapi import APIRouter, Depends, Header, HTTPException
import os
from app.services.database import SessionLocal
from fastapi.security import OAuth2PasswordRequestForm
from app.services.dbmodel import User
from sqlalchemy.orm import Session
from app.services.dbmodel import User,hash_password
from jwt import encode

auth_router = APIRouter()

ADMIN_KEY = os.getenv("ADMIN_KEY")



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_admin(admin_key):
    if admin_key == ADMIN_KEY:
        return True
    else:
        raise HTTPException(status_code=401, detail="Admin key is invalid Unauthorized")

@auth_router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(),db:Session = Depends(get_db)):
    try:
        user_id = db.query(User).filter(User.email == form_data.username).first()
        if not user_id:
            raise HTTPException(status_code=400, detail="Incorrect username or password")


    except:
        raise



