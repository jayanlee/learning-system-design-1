import threading
import time
import uuid

from fastapi import HTTPException

from app.config import settings

_lock = threading.Lock()
_hits: dict[str, list[float]] = {}


def reset() -> None:
    with _lock:
        _hits.clear()


def enforce(user_id: uuid.UUID) -> None:
    now = time.monotonic()
    key = str(user_id)
    with _lock:
        recent = [stamp for stamp in _hits.get(key, []) if now - stamp < 60]
        if len(recent) >= settings.rate_limit_per_minute:
            raise HTTPException(status_code=429, detail="Too many writes")
        recent.append(now)
        _hits[key] = recent
