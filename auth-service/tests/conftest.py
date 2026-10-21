import os

os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres@localhost:5432/sd_auth"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["COOKIE_SECURE"] = "false"
os.environ["RELAY_ENABLED"] = "false"
os.environ["BUS_DATABASE_URL"] = "postgresql+psycopg://postgres@localhost:5432/sd_bus"

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.database import engine


def ensure_database(name: str) -> None:
    with psycopg.connect("postgresql://postgres@localhost:5432/postgres", autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
        if exists is None:
            conn.execute(f'CREATE DATABASE "{name}"')


@pytest.fixture(scope="session", autouse=True)
def migrated() -> None:
    ensure_database("sd_auth")
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture(autouse=True)
def clean(migrated: None) -> None:
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE refresh_tokens, outbox, users CASCADE"))
