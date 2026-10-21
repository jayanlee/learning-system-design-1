from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import RefreshToken, User
from app.relay import enqueue
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.security import (
    bearer_scheme,
    get_current_user,
    hash_password,
    hash_refresh_token,
    issue_tokens,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=raw_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/api/auth",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key="refresh_token",
        path="/api/auth",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )


def _reject_refresh() -> JSONResponse:
    denied = JSONResponse(status_code=401, content={"detail": "Invalid or expired refresh token"})
    _clear_refresh_cookie(denied)
    return denied


def _normalize_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Name is required")
    return cleaned


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    email = body.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(
        name=_normalize_name(body.name),
        email=email,
        password_hash=hash_password(body.password),
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    try:
        db.flush()
        enqueue(
            db,
            "UserRegistered",
            {"user_id": str(user.id), "email": user.email, "name": user.name},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from None
    db.refresh(user)

    access_token, refresh_token, expires_in = issue_tokens(db, user)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token, refresh_token, expires_in = issue_tokens(db, user)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> TokenResponse | JSONResponse:
    now = datetime.now(timezone.utc)
    row = None
    if refresh_token:
        row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token)))
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        return _reject_refresh()

    user = db.scalar(select(User).where(User.id == row.user_id))
    if user is None:
        return _reject_refresh()

    row.revoked_at = now
    db.commit()

    access_token, new_refresh, expires_in = issue_tokens(db, user)
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    if refresh_token:
        row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token)))
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)
            db.commit()
    _clear_refresh_cookie(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserResponse)
def me(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    return get_current_user(credentials, db)


@router.get("/users", response_model=UserResponse)
def lookup_user(
    email: str,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    get_current_user(credentials, db)
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
