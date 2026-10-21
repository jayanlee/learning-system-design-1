from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.bus import build_publisher
from app.consumer import start_consumer, stop_consumer
from app.database import ping
from app.relay import relay_once, start_relay, stop_relay
from app.routers.tasks import router as task_router


def _relay_loop() -> None:
    from app.database import shards

    for shard in shards:
        relay_once(shard.Session, build_publisher(), "task-relay", lambda _event_type: "task-events")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_relay(_relay_loop)
    start_consumer()
    yield
    stop_consumer()
    stop_relay()


app = FastAPI(title="Task service", lifespan=lifespan)
app.include_router(task_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    try:
        ping()
    except OperationalError:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(status_code=200, content={"status": "ok"})
