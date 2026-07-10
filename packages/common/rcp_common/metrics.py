"""Tiny in-process metrics registry with Prometheus text rendering."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import Lock

_LOCK = Lock()


@dataclass
class _RequestStats:
    count: int = 0
    duration_sum: float = 0.0


_REQUESTS: dict[tuple[str, str, str, int], _RequestStats] = defaultdict(_RequestStats)


def record_http_request(
    *,
    service: str,
    method: str,
    path: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    key = (service, method, path, status_code)
    with _LOCK:
        stats = _REQUESTS[key]
        stats.count += 1
        stats.duration_sum += duration_seconds


def render_prometheus_metrics(
    service: str,
    *,
    database_connections: int | None = None,
) -> str:
    lines: list[str] = []
    lines.append("# HELP rcp_requests_total Total HTTP requests handled.")
    lines.append("# TYPE rcp_requests_total counter")
    lines.append("# HELP rcp_request_duration_seconds_total Total request duration in seconds.")
    lines.append("# TYPE rcp_request_duration_seconds_total counter")
    with _LOCK:
        for (svc, method, path, status_code), stats in sorted(_REQUESTS.items()):
            if svc != service:
                continue
            labels = f'service="{svc}",method="{method}",path="{path}",status="{status_code}"'
            lines.append(f"rcp_requests_total{{{labels}}} {stats.count}")
            lines.append(f"rcp_request_duration_seconds_total{{{labels}}} {stats.duration_sum:.6f}")
    if database_connections is not None:
        lines.append("# HELP rcp_database_connections Number of currently checked-out DB connections.")
        lines.append("# TYPE rcp_database_connections gauge")
        lines.append(f'rcp_database_connections{{service="{service}"}} {database_connections}')
    return "\n".join(lines) + "\n"