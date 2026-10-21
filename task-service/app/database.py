import hashlib
import os
import uuid
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Shard:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = create_engine(url, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)


def database_urls() -> list[str]:
    raw = os.environ.get("TASK_DATABASE_URLS", "").strip()
    if raw:
        return [part.strip() for part in raw.split(",") if part.strip()]
    return [settings.database_url]


shards: list[Shard] = [Shard(url) for url in database_urls()]
engine = shards[0].engine
SessionLocal = shards[0].Session


class Base(DeclarativeBase):
    pass


def shard_index(owner_id: uuid.UUID) -> int:
    digest = hashlib.sha256(str(owner_id).encode()).digest()
    return int.from_bytes(digest[:4], "big") % len(shards)


def session_for(owner_id: uuid.UUID) -> Session:
    return shards[shard_index(owner_id)].Session()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ping() -> None:
    for shard in shards:
        with shard.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
