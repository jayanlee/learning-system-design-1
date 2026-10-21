from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.bus import build_publisher
from app.database import SessionLocal, ping
from app.relay import relay_once, start_relay, stop_relay
from app.routers.auth import router as auth_router


def _relay_loop() -> None:
    relay_once(SessionLocal, build_publisher(), "auth-relay", lambda _event_type: "user-events")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_relay(_relay_loop)
    yield
    stop_relay()


app = FastAPI(title="Auth service", lifespan=lifespan)
app.include_router(auth_router)


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
