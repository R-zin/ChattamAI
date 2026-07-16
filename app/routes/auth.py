from fastapi import APIRouter, Depends, HTTPException,Header
from app.services.dbmodel import User

auth_router = APIRouter()

ADMIN_KEY = os.getenv("ADMIN_KEY")

def check_admin(admin_key):
    if admin_key == ADMIN_KEY:
        return True
    else:
        raise HTTPException(status_code=401,detail="Admin key is invalid Unauthorized")

