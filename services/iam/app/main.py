import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import routes_auth, routes_jwks
from app.core.config import settings
from app.core.keys import get_key_manager
from app.db.database import engine
from app.events.relay import start_relay
from app.models import Base

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(engine)
    get_key_manager()  # fail fast if the signing key is missing
    stop_relay = start_relay()
    yield
    stop_relay.set()


app = FastAPI(title="RCP IAM Service", lifespan=lifespan)
app.include_router(routes_auth.router)
app.include_router(routes_jwks.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
