"""Auth routes: register, login (JWT), and current-user dependencies.

Protection is **opt-in** and OFF by default so the credential-less CI smoke test
on ``GET /api/health`` keeps passing. Nothing here is applied to the RAG routes;
the :func:`require_auth` dependency is exported for the coordinator to attach to
``/api/ingest`` / ``/api/check`` later.

Environment (read via os.getenv with safe defaults; to be promoted into
``app.config.Settings`` by the coordinator):

- ``SECRET_KEY``     — JWT signing key. Override in production.
- ``AUTH_ALGORITHM`` — JWT algorithm (default ``HS256``).
- ``TIME_OUT``       — access-token TTL in seconds (default ``3600``).
- ``AUTH_REQUIRED``  — "true"/"1"/"yes" makes :func:`require_auth` enforce a token.
- ``ADMIN_KEY``      — if set, ``POST /auth/register`` requires a matching
  ``X-Admin-Key`` header. If unset, registration is open (self-service).
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.database import SessionLocal
from app.services.dbmodel import (
    AUTH_ALGORITHM,
    DEFAULT_TIME_OUT,
    SECRET_KEY,
    User,
    create_access_token,
    decode_access_token,
    hash_password,
    new_id,
    verify_password,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])

# tokenUrl points at the OAuth2 "password" login so Swagger's Authorize flow works.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

_TRUTHY = {"1", "true", "yes", "on"}


def _auth_required() -> bool:
    return os.getenv("AUTH_REQUIRED", "").strip().lower() in _TRUTHY


def _admin_key() -> Optional[str]:
    return os.getenv("ADMIN_KEY")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


@auth_router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="register_user",
)
def register(
    payload: RegisterRequest = Body(...),
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> UserResponse:
    """Create a user with a bcrypt-hashed password.

    Gating: when the ``ADMIN_KEY`` env var is set, the request must send a
    matching ``X-Admin-Key`` header. When ``ADMIN_KEY`` is unset, registration is
    open (self-service) so the very first user can be created. Documented choice:
    admin-key-if-configured, else open.
    """
    if _admin_key() is not None and x_admin_key != _admin_key():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin key is invalid"
        )

    if _get_user_by_email(db, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user = User(
        user_id=new_id(),
        email=payload.email,
        password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@auth_router.post("/login", response_model=TokenResponse, operation_id="login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Verify credentials and return a JWT (OAuth2 password form; used by /docs)."""
    user = _get_user_by_email(db, form_data.username)
    if user is None or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user_id=user.user_id, email=user.email)
    return TokenResponse(access_token=token, expires_in=DEFAULT_TIME_OUT)


@auth_router.post(
    "/login/json", response_model=TokenResponse, operation_id="login_json"
)
def login_json(
    payload: LoginRequest = Body(...), db: Session = Depends(get_db)
) -> TokenResponse:
    """JSON-body login (convenience for non-OAuth2 clients)."""
    user = _get_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user_id=user.user_id, email=user.email)
    return TokenResponse(access_token=token, expires_in=DEFAULT_TIME_OUT)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode the bearer JWT and load the corresponding user.

    Raises 401 when the token is missing/invalid/expired or the user no longer
    exists. Independent of ``AUTH_REQUIRED`` — it always enforces the token.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exc
    try:
        payload = decode_access_token(token)
    except Exception:  # jose.JWTError and friends
        raise credentials_exc
    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exc
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise credentials_exc
    return user


def require_auth(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Opt-in guard for protected endpoints. OFF by default.

    When ``AUTH_REQUIRED`` is falsy (default) this is a no-op returning ``None``,
    so existing behavior and the CI smoke test are unchanged. When truthy it
    enforces :func:`get_current_user` and returns the authenticated ``User``.

    Exported for the coordinator to attach to mutating/paid routes, e.g.::

        @router.post("/ingest", dependencies=[Depends(require_auth)])
    """
    if not _auth_required():
        return None
    return get_current_user(token=token, db=db)


@auth_router.get("/me", response_model=UserResponse, operation_id="read_me")
def read_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user. Always requires a valid token."""
    return UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        created_at=(
            current_user.created_at.isoformat() if current_user.created_at else None
        ),
    )


# Surface active auth config for logs/debug (never the secret value).
AUTH_CONFIG = {"algorithm": AUTH_ALGORITHM, "ttl_seconds": DEFAULT_TIME_OUT}
_ = SECRET_KEY  # re-exported for the coordinator; keep linters quiet
