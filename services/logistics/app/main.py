from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from rcp_common.logging import configure_logging
from rcp_common.middleware import RequestContextMiddleware

from app.api import routes_inventory, routes_requests, routes_volunteers
from app.core.config import settings
from app.db.database import engine
from app.events.consumers.iam import start_consumer
from app.events.relay import start_relay
from app.models import Base

configure_logging(settings.SERVICE_NAME, settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(engine)
    stop_relay = start_relay()
    stop_consumer = start_consumer()
    yield
    stop_relay.set()
    stop_consumer.set()


app = FastAPI(title="RCP Logistics Service", lifespan=lifespan)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_requests.router)
app.include_router(routes_inventory.router)
app.include_router(routes_volunteers.router)


def _database_ready() -> bool:
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/liveness")
def liveness():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/readiness")
def readiness():
    if _database_ready():
        return {"status": "ok", "service": settings.SERVICE_NAME, "checks": {"database": "ok"}}
    return JSONResponse(
        status_code=503,
        content={
            "status": "degraded",
            "service": settings.SERVICE_NAME,
            "checks": {"database": "unavailable"},
        },
    )
