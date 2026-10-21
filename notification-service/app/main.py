from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.consumer import start_consumer, stop_consumer
from app.database import ping
from app.routers.notifications import router as notification_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_consumer()
    yield
    stop_consumer()


app = FastAPI(title="Notification service", lifespan=lifespan)
app.include_router(notification_router)


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
