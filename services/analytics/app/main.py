from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rcp_common.logging import configure_logging
from rcp_common.middleware import RequestContextMiddleware

from app.api import routes_reports
from app.core.config import settings

configure_logging(settings.SERVICE_NAME, settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # schema_analytics objects are managed by Alembic (make migrate-analytics);
    # the logistics read model is owned and migrated by the logistics service.
    yield


app = FastAPI(title="RCP Analytics Service", lifespan=lifespan)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_reports.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
