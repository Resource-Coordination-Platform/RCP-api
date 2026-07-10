"""Request forwarding: match the longest route prefix, forward verbatim.

Authentication forwarding = the Authorization header passes through
untouched; each service verifies the JWT itself against IAM's JWKS. The
gateway never decodes or mints tokens.
"""

import logging

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import ROUTE_TABLE, settings

logger = logging.getLogger(__name__)

# hop-by-hop headers must not be forwarded (RFC 9110 §7.6.1)
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}

_client = httpx.AsyncClient(timeout=settings.PROXY_TIMEOUT_SECONDS)


def resolve_upstream(path: str) -> str | None:
    matches = [prefix for prefix in ROUTE_TABLE if path == prefix or path.startswith(prefix + "/")]
    if not matches:
        return None
    return ROUTE_TABLE[max(matches, key=len)]


async def forward(request: Request) -> Response:
    upstream = resolve_upstream(request.url.path)
    if upstream is None:
        return JSONResponse({"detail": "No route for path"}, status_code=404)

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in _HOP_BY_HOP
    }
    traceparent = getattr(request.state, "traceparent", None)
    if traceparent:
        headers["traceparent"] = traceparent
    if request.client:
        headers["X-Forwarded-For"] = request.client.host

    try:
        upstream_response = await _client.request(
            request.method,
            f"{upstream}{request.url.path}",
            params=request.url.query or None,
            headers=headers,
            content=await request.body(),
        )
    except httpx.HTTPError as exc:
        logger.error("upstream %s unreachable: %s", upstream, exc)
        return JSONResponse({"detail": "Upstream service unavailable"}, status_code=502)

    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in _HOP_BY_HOP
    }
    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=upstream_response.headers.get("content-type"),
    )


async def close_client() -> None:
    await _client.aclose()
