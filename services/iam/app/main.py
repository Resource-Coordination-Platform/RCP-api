from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.responses import JSONResponse
from rcp_common.logging import configure_logging
from rcp_common.middleware import RequestContextMiddleware
from rcp_common.metrics import render_prometheus_metrics

from app.api import routes_auth, routes_jwks
from app.core.config import settings
from app.core.keys import get_key_manager
from app.db.database import engine
from app.events.relay import start_relay
from app.models import Base

configure_logging(settings.SERVICE_NAME, settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(engine)
    get_key_manager()  # fail fast if the signing key is missing
    stop_relay = start_relay()
    yield
    stop_relay.set()


app = FastAPI(title="RCP IAM Service", lifespan=lifespan)
app.state.service_name = settings.SERVICE_NAME

app.add_middleware(RequestContextMiddleware)

app.include_router(routes_auth.router)
app.include_router(routes_jwks.router)


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


@app.get("/metrics")
def metrics():
    checked_out = getattr(engine.pool, "checkedout", lambda: 0)()
    return Response(
        render_prometheus_metrics(settings.SERVICE_NAME, database_connections=checked_out),
        media_type="text/plain; version=0.0.4",
    )


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
