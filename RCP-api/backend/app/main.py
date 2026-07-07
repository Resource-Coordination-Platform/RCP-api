from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_auth,
    routes_inventory,
    routes_reports,
    routes_requests,
    routes_volunteers,
)
from app.core.config import settings
from app.middlewares.tenant_context import TenantContextMiddleware
from app.websockets import routes as ws_routes

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantContextMiddleware)

app.include_router(routes_auth.router)
app.include_router(routes_requests.router)
app.include_router(routes_inventory.router)
app.include_router(routes_volunteers.router)
app.include_router(routes_reports.router)
app.include_router(ws_routes.router)


@app.get("/health")
def health():
    return {"status": "ok"}
