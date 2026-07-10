"""Request-scoped middleware shared by all FastAPI services."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from rcp_common.metrics import record_http_request

_access_log = logging.getLogger("rcp.access")

REQUEST_ID_HEADER = "X-Request-ID"
TRACEPARENT_HEADER = "traceparent"


def _parse_traceparent(value: str | None) -> tuple[str, str]:
    if value:
        parts = value.split("-")
        if len(parts) == 4 and len(parts[1]) == 32 and len(parts[2]) == 16:
            return parts[1], uuid.uuid4().hex[:16]
    return uuid.uuid4().hex, uuid.uuid4().hex[:16]


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Propagates X-Request-ID and emits one structured access-log line per request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        trace_id, span_id = _parse_traceparent(request.headers.get(TRACEPARENT_HEADER))
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        request.state.traceparent = f"00-{trace_id}-{span_id}-01"
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[TRACEPARENT_HEADER] = request.state.traceparent
        _access_log.info(
            "%s %s -> %s in %sms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            extra={"request_id": request_id, "trace_id": trace_id},
        )
        record_http_request(
            service=getattr(request.app.state, "service_name", request.app.title),
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_seconds=time.perf_counter() - started,
        )
        return response
