from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from rcp_common.logging import configure_logging
from rcp_common.metrics import render_prometheus_metrics
from rcp_common.middleware import RequestContextMiddleware

from app.api import routes_assignments, routes_events, routes_profiles
from app.core.config import settings
from app.db.database import engine
from app.events.consumers.disaster import start_consumer as start_disaster_consumer
from app.events.consumers.iam import start_consumer as start_iam_consumer
from app.events.relay import start_relay
from app.models import Base

configure_logging(settings.SERVICE_NAME, settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(engine)
    stop_relay = start_relay()
    stop_iam = start_iam_consumer()
    stop_disaster = start_disaster_consumer()
    yield
    stop_relay.set()
    stop_iam.set()
    stop_disaster.set()


app = FastAPI(title="RCP Volunteer Service", lifespan=lifespan)
app.state.service_name = settings.SERVICE_NAME

# Browser traffic reaches this service only through the gateway, which owns
# the single CORS layer — configuring it here too would double the headers.
app.add_middleware(RequestContextMiddleware)

app.include_router(routes_profiles.router)
app.include_router(routes_events.router)
app.include_router(routes_assignments.router)


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
