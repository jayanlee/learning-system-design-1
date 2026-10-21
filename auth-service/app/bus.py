import json
import os
import uuid
from datetime import datetime, timezone

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

DEFAULT_BUS_URL = "postgresql+psycopg://postgres@localhost:5432/sd_bus"

_engine: Engine | None = None


def bus_url() -> str:
    return os.environ.get("BUS_DATABASE_URL", DEFAULT_BUS_URL)


def _database_name(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def ensure_bus() -> Engine:
    global _engine
    if _engine is not None:
        return _engine
    name = _database_name(bus_url())
    admin = bus_url().rsplit("/", 1)[0] + "/postgres"
    admin = admin.replace("postgresql+psycopg", "postgresql")
    with psycopg.connect(admin, autocommit=True) as connection:
        exists = connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
        if exists is None:
            try:
                connection.execute(f'CREATE DATABASE "{name}"')
            except psycopg.errors.UniqueViolation:
                # Another process created sd_bus between the check and the insert.
                pass
    _engine = create_engine(bus_url(), pool_pre_ping=True)
    with _engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id UUID PRIMARY KEY,
                    queue_name TEXT NOT NULL,
                    body JSONB NOT NULL,
                    receive_count INTEGER NOT NULL DEFAULT 0,
                    visible_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS dead_letters (
                    id UUID PRIMARY KEY,
                    queue_name TEXT NOT NULL,
                    body JSONB NOT NULL,
                    receive_count INTEGER NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )
    return _engine


def publish(queue_name: str, body: dict) -> None:
    engine = ensure_bus()
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO messages (id, queue_name, body, receive_count, visible_at, created_at)
                VALUES (:id, :queue_name, CAST(:body AS jsonb), 0, :now, :now)
                """
            ),
            {"id": uuid.uuid4(), "queue_name": queue_name, "body": json.dumps(body), "now": now},
        )


def receive(queue_name: str, visibility_seconds: int = 30, max_receives: int = 5) -> dict | None:
    engine = ensure_bus()
    while True:
        with engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT id, body, receive_count
                    FROM messages
                    WHERE queue_name = :queue_name AND visible_at <= now()
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """
                ),
                {"queue_name": queue_name},
            ).mappings().first()
            if row is None:
                return None
            next_count = int(row["receive_count"]) + 1
            if next_count > max_receives:
                connection.execute(
                    text(
                        """
                        INSERT INTO dead_letters (id, queue_name, body, receive_count, created_at)
                        VALUES (:id, :queue_name, CAST(:body AS jsonb), :receive_count, now())
                        """
                    ),
                    {
                        "id": row["id"],
                        "queue_name": queue_name,
                        "body": json.dumps(row["body"]),
                        "receive_count": next_count,
                    },
                )
                connection.execute(text("DELETE FROM messages WHERE id = :id"), {"id": row["id"]})
                continue
            connection.execute(
                text(
                    """
                    UPDATE messages
                    SET receive_count = :receive_count,
                        visible_at = now() + make_interval(secs => :visibility_seconds)
                    WHERE id = :id
                    """
                ),
                {"id": row["id"], "receive_count": next_count, "visibility_seconds": visibility_seconds},
            )
            body = row["body"]
            if isinstance(body, str):
                body = json.loads(body)
            return {"id": row["id"], "body": body, "receive_count": next_count}


def make_visible(message_id: uuid.UUID) -> None:
    with ensure_bus().begin() as connection:
        connection.execute(
            text("UPDATE messages SET visible_at = now() - interval '1 second' WHERE id = :id"),
            {"id": message_id},
        )


def delete_message(message_id: uuid.UUID) -> None:
    with ensure_bus().begin() as connection:
        connection.execute(text("DELETE FROM messages WHERE id = :id"), {"id": message_id})


def count_messages(queue_name: str) -> int:
    with ensure_bus().connect() as connection:
        value = connection.execute(
            text("SELECT count(*) FROM messages WHERE queue_name = :queue_name"),
            {"queue_name": queue_name},
        ).scalar_one()
    return int(value)


def count_dead_letters(queue_name: str) -> int:
    with ensure_bus().connect() as connection:
        value = connection.execute(
            text("SELECT count(*) FROM dead_letters WHERE queue_name = :queue_name"),
            {"queue_name": queue_name},
        ).scalar_one()
    return int(value)


def truncate_bus() -> None:
    ensure_bus()
    with ensure_bus().begin() as connection:
        connection.execute(text("TRUNCATE messages, dead_letters"))


class LocalPublisher:
    def publish(self, queue_name: str, body: dict) -> None:
        publish(queue_name, body)


def driver() -> str:
    return os.environ.get("BUS_DRIVER", "local")


class EventBridgePublisher:
    """Cloud copy of LocalPublisher. EventBridge routes by detail-type; the queue name is unused."""

    def __init__(self) -> None:
        import boto3

        self.client = boto3.client("events", region_name=os.environ.get("AWS_REGION", "ap-southeast-2"))
        self.bus_name = os.environ["EVENT_BUS_NAME"]
        self.source = os.environ.get("EVENT_SOURCE", "task.service")

    def publish(self, queue_name: str, body: dict) -> None:
        self.client.put_events(
            Entries=[
                {
                    "EventBusName": self.bus_name,
                    "Source": self.source,
                    "DetailType": str(body.get("event_type", queue_name)),
                    "Detail": json.dumps(body),
                }
            ]
        )


def build_publisher() -> LocalPublisher | EventBridgePublisher:
    if driver() == "aws":
        return EventBridgePublisher()
    return LocalPublisher()


def _queue_url(queue_name: str) -> str:
    urls = {
        "user-events": os.environ.get("USER_EVENTS_QUEUE_URL", ""),
        "task-events": os.environ.get("TASK_EVENTS_QUEUE_URL", ""),
    }
    url = urls.get(queue_name, "")
    if not url:
        raise RuntimeError(f"Missing queue URL for {queue_name}")
    return url


def take_one(queue_name: str) -> dict | None:
    if driver() != "aws":
        return receive(queue_name)
    import boto3

    client = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "ap-southeast-2"))
    response = client.receive_message(
        QueueUrl=_queue_url(queue_name),
        MaxNumberOfMessages=1,
        WaitTimeSeconds=1,
    )
    messages = response.get("Messages") or []
    if not messages:
        return None
    raw = json.loads(messages[0]["Body"])
    detail = raw.get("detail", raw)
    if isinstance(detail, str):
        detail = json.loads(detail)
    return {"id": None, "receipt_handle": messages[0]["ReceiptHandle"], "body": detail, "queue_name": queue_name}


def ack(message: dict) -> None:
    if driver() != "aws":
        delete_message(message["id"])
        return
    import boto3

    boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "ap-southeast-2")).delete_message(
        QueueUrl=_queue_url(str(message["queue_name"])),
        ReceiptHandle=message["receipt_handle"],
    )

