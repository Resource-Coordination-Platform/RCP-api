from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from rcp_common.logging import configure_logging
from rcp_common.middleware import RequestContextMiddleware
from rcp_common.metrics import render_prometheus_metrics

from app.api import routes_reports
from app.core.config import settings
from app.db.database import engine
from app.events.consumer import start_consumer

configure_logging(settings.SERVICE_NAME, settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # schema_analytics objects are managed by Alembic (make migrate-analytics);
    # the analytics read model is owned and migrated by this service.
    stop_consumer = start_consumer()
    yield
    stop_consumer.set()


app = FastAPI(title="RCP Analytics Service", lifespan=lifespan)
app.state.service_name = settings.SERVICE_NAME

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_reports.router)


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
