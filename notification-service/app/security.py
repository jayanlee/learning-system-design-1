import uuid

import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


def get_user_id(credentials: HTTPAuthorizationCredentials | None) -> uuid.UUID:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
