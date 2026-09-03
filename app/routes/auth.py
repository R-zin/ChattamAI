"""Auth routes: register, login (JWT), and current-user dependencies.

Protection is **opt-in** and OFF by default so the credential-less CI smoke test
on ``GET /api/health`` keeps passing. Nothing here is applied to the RAG routes;
the :func:`require_auth` dependency is exported for the coordinator to attach to
``/api/ingest`` / ``/api/check`` later.

Environment (via ``app.config.Settings``):

- ``SECRET_KEY``     — JWT signing key. Override in production.
- ``AUTH_ALGORITHM`` — JWT algorithm (default ``HS256``).
- ``TIME_OUT``       — access-token TTL in seconds (default ``3600``).
- ``AUTH_REQUIRED``  — "true"/"1"/"yes" makes :func:`require_auth` enforce a token.
- ``ADMIN_KEY``      — if set, ``POST /auth/register`` requires a matching
  ``X-Admin-Key`` header. If unset, registration is open (self-service).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import get_settings
from app.schemas import (
    LoginRequest,
    OtpRequiredResponse,
    RegisterRequest,
    TokenResponse,
    TotpDisableRequest,
    TotpEnableRequest,
    TotpEnableResponse,
    TotpRecoverRequest,
    TotpSetupResponse,
    TotpStatusResponse,
    TotpVerifyRequest,
    UserResponse,
)
from app.services.database import SessionLocal
from app.services.dbmodel import (
    RecoveryCode,
    User,
    create_access_token,
    create_otp_challenge_token,
    decode_access_token,
    decode_otp_challenge_token,
    generate_recovery_codes,
    hash_password,
    hash_recovery_code,
    new_id,
    verify_password,
)
from app.services.totp import (
    new_totp_secret,
    provisioning_uri,
    qr_png_data_uri,
    verify_totp,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])

# tokenUrl points at the OAuth2 "password" login so Swagger's Authorize flow works.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _token_ttl() -> int:
    return int(get_settings().session_timeout_seconds)


def _auth_required() -> bool:
    return bool(get_settings().auth_required)


def _admin_key() -> Optional[str]:
    return get_settings().admin_key


def _totp_required() -> bool:
    """Server-wide toggle. Read from ``os.environ`` AT REQUEST TIME (not via the
    cached ``Settings``): pydantic evaluates a ``Settings`` field default only once
    at class-definition/import, so a ``Settings`` attribute can never reflect a
    later-set env var. Env-var reading matches how the toggle is expected to be
    driven (deployment env) and keeps tests able to flip it without a reboot."""
    import os

    return os.getenv("TOTP_REQUIRED", "").strip().lower() in ("1", "true", "yes", "on")


def _otp_challenge_ttl() -> int:
    return int(getattr(get_settings(), "otp_challenge_ttl_seconds", 300))


def _totp_issuer() -> str:
    return str(getattr(get_settings(), "totp_issuer", "ChattamAI"))


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
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Create a user with a bcrypt-hashed password.

    Gating: when the ``ADMIN_KEY`` env var is set, the request must send a
    matching ``X-Admin-Key`` header. When ``ADMIN_KEY`` is unset, registration is
    open (self-service) so the very first user can be created. Documented choice:
    admin-key-if-configured, else open.
    """
    admin_key = _admin_key()
    if admin_key is not None and x_admin_key != admin_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration requires a valid X-Admin-Key header",
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
        totp_enabled=bool(user.totp_enabled),
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
    return TokenResponse(access_token=token, expires_in=_token_ttl())


@auth_router.post("/login/json", response_model=None, operation_id="login_json")
def login_json(payload: LoginRequest = Body(...), db: Session = Depends(get_db)) -> Any:
    """JSON-body login (convenience for non-OAuth2 clients).

    Returns a normal ``TokenResponse`` when the user has no 2FA. When the user
    has TOTP enabled (or ``TOTP_REQUIRED`` is on and they must enrol), returns an
    ``OtpRequiredResponse`` carrying a short-lived challenge token instead — the
    client completes the login via ``POST /auth/totp/verify`` (or ``recover``).
    """
    user = _get_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.totp_enabled or _totp_required():
        setup_required = not bool(user.totp_enabled)
        return OtpRequiredResponse(
            otp_setup_required=setup_required,
            otp_token=create_otp_challenge_token(
                user.user_id, user.email, setup_required=setup_required
            ),
            expires_in=_otp_challenge_ttl(),
        )
    token = create_access_token(user_id=user.user_id, email=user.email)
    return TokenResponse(access_token=token, expires_in=_token_ttl())


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
    # A TOTP challenge token is pre-auth and single-purpose: it must never act
    # as an access token even though it carries a valid ``sub``.
    if payload.get("purpose") == "totp":
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
    db: Session = next(get_db())
    try:
        return get_current_user(token=token, db=db)
    finally:
        db.close()


# --- TOTP / 2FA endpoints ----------------------------------------------------
#
# Sits between require_auth and __all__ on purpose: routes are evaluated in the
# order FastAPI scans them, but this block depends only on _totp_required()
# (defined above) and the shared deps, so placement here is safe and keeps the
# 2FA code together.


def _totp_actor(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Actor for setup/enable: an authenticated user OR a forced-enroll login.

    Accepts (a) a normal access token (``get_current_user``), or (b) a TOTP
    challenge token whose ``setup`` claim is True — the path a TOTP_REQUIRED
    unenrolled user takes before they have any access token. Everything else is
    rejected 401."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exc
    try:
        payload = decode_access_token(token)
    except Exception:
        raise credentials_exc
    if payload.get("purpose") == "totp" and not payload.get("setup"):
        raise credentials_exc
    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exc
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise credentials_exc
    return user


def _load_challenge_user(otp_token: str, db: Session) -> User:
    """Decode a TOTP challenge token to its user, rejecting non-challenge tokens."""
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired login challenge",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_otp_challenge_token(otp_token)
    except Exception:
        raise exc
    user = db.query(User).filter(User.user_id == payload.get("sub")).first()
    if user is None:
        raise exc
    return user


@auth_router.post(
    "/totp/setup", response_model=TotpSetupResponse, operation_id="totp_setup"
)
def totp_setup(
    user: User = Depends(_totp_actor), db: Session = Depends(get_db)
) -> TotpSetupResponse:
    """Generate a fresh TOTP secret (NOT yet enabled) and return a scannable QR."""
    secret = new_totp_secret()
    user.totp_secret = secret
    db.commit()
    uri = provisioning_uri(secret, user.email, _totp_issuer())
    return TotpSetupResponse(
        otpauth_uri=uri, qr_png_data_uri=qr_png_data_uri(uri), secret=secret
    )


@auth_router.post(
    "/totp/enable", response_model=TotpEnableResponse, operation_id="totp_enable"
)
def totp_enable(
    payload: TotpEnableRequest = Body(...),
    user: User = Depends(_totp_actor),
    db: Session = Depends(get_db),
) -> TotpEnableResponse:
    """Confirm the secret with a first valid code, enrol, and issue recovery codes."""
    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Call /auth/totp/setup before enabling",
        )
    if not verify_totp(user.totp_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid authenticator code"
        )
    user.totp_enabled = True
    # Replace any prior codes so a re-enrolment yields a fresh, single-use set.
    db.query(RecoveryCode).filter(RecoveryCode.user_id == user.user_id).delete(
        synchronize_session=False
    )
    codes = generate_recovery_codes()
    db.add_all(
        [
            RecoveryCode(
                user_id=user.user_id, code_id=new_id(), code_hash=hash_recovery_code(c)
            )
            for c in codes
        ]
    )
    db.commit()
    return TotpEnableResponse(enabled=True, recovery_codes=codes)


@auth_router.post(
    "/totp/verify", response_model=TokenResponse, operation_id="totp_verify"
)
def totp_verify(
    payload: TotpVerifyRequest = Body(...), db: Session = Depends(get_db)
) -> TokenResponse:
    """Exchange a challenge token + authenticator code for a real access token."""
    user = _load_challenge_user(payload.otp_token, db)
    try:
        setup = bool(decode_otp_challenge_token(payload.otp_token).get("setup"))
    except Exception:
        setup = False
    if setup and not user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Two-factor enrolment required before login (see /auth/totp/setup)",
        )
    if not user.totp_secret or not verify_totp(user.totp_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authenticator code",
        )
    return TokenResponse(
        access_token=create_access_token(user_id=user.user_id, email=user.email),
        expires_in=_token_ttl(),
    )


@auth_router.post(
    "/totp/recover", response_model=TokenResponse, operation_id="totp_recover"
)
def totp_recover(
    payload: TotpRecoverRequest = Body(...), db: Session = Depends(get_db)
) -> TokenResponse:
    """Exchange a challenge token + one unused recovery code for an access token."""
    user = _load_challenge_user(payload.otp_token, db)
    code_hash = hash_recovery_code(payload.recovery_code)
    row = (
        db.query(RecoveryCode)
        .filter(
            RecoveryCode.user_id == user.user_id,
            RecoveryCode.code_hash == code_hash,
            RecoveryCode.used_at.is_(None),
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery code"
        )
    from datetime import datetime as _dt

    row.used_at = _dt.utcnow()  # single-use
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user_id=user.user_id, email=user.email),
        expires_in=_token_ttl(),
    )


@auth_router.post(
    "/totp/disable", response_model=TotpStatusResponse, operation_id="totp_disable"
)
def totp_disable(
    payload: TotpDisableRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TotpStatusResponse:
    """Turn 2FA off. Requires BOTH the password and a current authenticator code
    so a stolen session token alone can't disarm the account."""
    if not verify_password(payload.password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect password"
        )
    if current_user.totp_enabled and not verify_totp(
        current_user.totp_secret, payload.code
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid authenticator code"
        )
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.query(RecoveryCode).filter(RecoveryCode.user_id == current_user.user_id).delete(
        synchronize_session=False
    )
    db.commit()
    return TotpStatusResponse(
        totp_enabled=False,
        totp_required=_totp_required(),
        recovery_codes_remaining=0,
    )


@auth_router.get(
    "/totp/status", response_model=TotpStatusResponse, operation_id="totp_status"
)
def totp_status(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TotpStatusResponse:
    """Report the caller's 2FA state (drives the Settings > Security UI)."""
    remaining = (
        db.query(RecoveryCode)
        .filter(
            RecoveryCode.user_id == current_user.user_id,
            RecoveryCode.used_at.is_(None),
        )
        .count()
    )
    return TotpStatusResponse(
        totp_enabled=bool(current_user.totp_enabled),
        totp_required=_totp_required(),
        recovery_codes_remaining=remaining,
    )


__all__ = [
    "auth_router",
    "oauth2_scheme",
    "get_db",
    "get_current_user",
    "require_auth",
    "auth_config",
]


@auth_router.get("/me", response_model=UserResponse, operation_id="read_me")
def read_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user. Always requires a valid token."""
    return UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        created_at=(
            current_user.created_at.isoformat() if current_user.created_at else None
        ),
        totp_enabled=bool(current_user.totp_enabled),
    )


def auth_config() -> dict:
    """Surface active auth config for logs/debug (never the secret value)."""
    return {"algorithm": get_settings().auth_algorithm, "ttl_seconds": _token_ttl()}
