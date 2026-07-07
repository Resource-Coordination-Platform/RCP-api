import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_inventory, routes_reports, routes_requests, routes_volunteers
from app.core.config import settings
from app.db.database import engine
from app.events.consumers.iam import start_consumer
from app.events.relay import start_relay
from app.models import Base

logging.basicConfig(level=logging.INFO)


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
app.include_router(routes_reports.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
