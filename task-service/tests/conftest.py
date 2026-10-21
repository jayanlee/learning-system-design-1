import os
import subprocess
import sys
from pathlib import Path

os.environ["JWT_SECRET"] = "test-secret"
os.environ["RATE_LIMIT_PER_MINUTE"] = "5"
os.environ["RELAY_ENABLED"] = "false"
os.environ["CONSUMER_ENABLED"] = "false"
os.environ["BUS_DATABASE_URL"] = "postgresql+psycopg://postgres@localhost:5432/sd_bus"
SHARD_URLS = [
    "postgresql+psycopg://postgres@localhost:5432/sd_task_0",
    "postgresql+psycopg://postgres@localhost:5432/sd_task_1",
]
os.environ["DATABASE_URL"] = SHARD_URLS[0]
os.environ["TASK_DATABASE_URLS"] = ",".join(SHARD_URLS)

import psycopg
import pytest
from sqlalchemy import text

from app.database import shards
from app.rate_limit import reset

ROOT = Path(__file__).resolve().parents[1]


def ensure_database(name: str) -> None:
    with psycopg.connect("postgresql://postgres@localhost:5432/postgres", autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
        if exists is None:
            conn.execute(f'CREATE DATABASE "{name}"')


def migrate(url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    subprocess.check_call([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env)


@pytest.fixture(scope="session", autouse=True)
def migrated() -> None:
    for url in SHARD_URLS:
        ensure_database(url.rsplit("/", 1)[-1])
        migrate(url)


@pytest.fixture(autouse=True)
def clean(migrated: None) -> None:
    reset()
    for shard in shards:
        with shard.engine.begin() as connection:
            connection.execute(text("TRUNCATE idempotency_keys, outbox, processed_events, tasks, user_directory CASCADE"))
