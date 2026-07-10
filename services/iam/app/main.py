from contextlib import asynccontextmanager

from fastapi import FastAPI
from rcp_common.logging import configure_logging
from rcp_common.middleware import RequestContextMiddleware

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

app.add_middleware(RequestContextMiddleware)

app.include_router(routes_auth.router)
app.include_router(routes_jwks.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
