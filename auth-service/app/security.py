import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import RefreshToken, User

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    raw = password.encode()
    if len(raw) > 72:
        raise HTTPException(status_code=422, detail="Password is too long")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user.id), "email": user.email, "name": user.name, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_tokens(db: Session, user: User) -> tuple[str, str, int]:
    access_token = create_access_token(user)
    raw_refresh = generate_refresh_token()
    now = datetime.now(timezone.utc)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
            created_at=now,
        )
    )
    db.commit()
    return access_token, raw_refresh, settings.access_token_expire_minutes * 60


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing token")
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = uuid.UUID(payload.get("sub", ""))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user
