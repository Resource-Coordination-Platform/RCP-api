import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi import WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from rcp_clients import AnalyticsClient, IAMClient, LogisticsClient, ServiceClient
from rcp_common.logging import configure_logging
from rcp_common.middleware import RequestContextMiddleware
from rcp_common.metrics import render_prometheus_metrics

from app.core.config import ROUTE_TABLE, settings
from app.proxy import close_client, forward
from app.ratelimit import RateLimitMiddleware
from app.ws_proxy import proxy_ws

configure_logging(settings.SERVICE_NAME, settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_client()


app = FastAPI(title="RCP API Gateway", lifespan=lifespan)
app.state.service_name = settings.SERVICE_NAME

app.add_middleware(RequestContextMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_service_clients: dict[str, ServiceClient] = {
    "iam": IAMClient(settings.IAM_URL),
    "logistics": LogisticsClient(settings.LOGISTICS_URL),
    "analytics": AnalyticsClient(settings.ANALYTICS_URL),
    "volunteer": ServiceClient(settings.VOLUNTEER_URL),
    "rto": ServiceClient(settings.RTO_URL),
}


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/metrics")
async def metrics():
    return Response(render_prometheus_metrics(settings.SERVICE_NAME), media_type="text/plain; version=0.0.4")


@app.get("/liveness")
async def liveness():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/readiness")
async def readiness():
    """Aggregated platform readiness — the gateway's fan-out endpoint."""
    names = list(_service_clients)
    results = await asyncio.gather(*(_service_clients[n].health() for n in names))
    statuses = dict(zip(names, results))
    overall = "ok" if all(s.get("status") == "ok" for s in statuses.values()) else "degraded"
    return {"status": overall, "services": statuses}


@app.get("/health/services")
async def services_health():
    return await readiness()


@app.get("/routes")
async def routes():
    """The active routing table (debugging aid; no secrets involved)."""
    return ROUTE_TABLE


@app.websocket("/ws")
async def ws_proxy(websocket: WebSocket):
    await proxy_ws(websocket)


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def proxy(path: str, request: Request):
    return await forward(request)
