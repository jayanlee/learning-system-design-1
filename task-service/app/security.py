import uuid
from typing import NamedTuple

import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


class Principal(NamedTuple):
    user_id: uuid.UUID
    email: str
    name: str


def get_principal(credentials: HTTPAuthorizationCredentials | None) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        return Principal(
            user_id=uuid.UUID(payload["sub"]),
            email=str(payload["email"]),
            name=str(payload["name"]),
        )
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
