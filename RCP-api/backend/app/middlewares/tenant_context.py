"""Resolves the tenant for each request from the X-Tenant-Slug header
(or subdomain, when deployed) and stores it on request.state so routes
and services can scope every query to one tenant."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

TENANT_HEADER = "X-Tenant-Slug"


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.tenant_slug = request.headers.get(TENANT_HEADER)
        return await call_next(request)
