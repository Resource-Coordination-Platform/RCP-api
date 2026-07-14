from fastapi.testclient import TestClient

from app.main import app, _service_clients
from app.proxy import resolve_upstream
from app.core.config import ROUTE_TABLE, settings
from app.ws_proxy import _upstream_ws_url


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "api-gateway"


def test_probe_endpoints_exist():
    with TestClient(app) as client:
        readiness = client.get("/readiness")
        liveness = client.get("/liveness")
    assert readiness.status_code == 200
    assert readiness.json()["status"] in {"ok", "degraded"}
    assert liveness.status_code == 200


def test_route_resolution():
    assert resolve_upstream("/api/auth/login") == settings.IAM_URL
    assert resolve_upstream("/.well-known/jwks.json") == settings.IAM_URL
    assert resolve_upstream("/api/requests") == settings.LOGISTICS_URL
    assert resolve_upstream("/api/inventory/abc") == settings.LOGISTICS_URL
    assert resolve_upstream("/api/volunteers/xyz") == settings.LOGISTICS_URL
    assert resolve_upstream("/api/volunteer/events") == settings.VOLUNTEER_URL
    assert resolve_upstream("/api/reports/need-vs-fulfillment") == settings.ANALYTICS_URL
    assert resolve_upstream("/api/unknown") is None


def test_readiness_covers_every_routed_service():
    """Every upstream in the route table must be part of the aggregated
    readiness fan-out, so /readiness can never report ok while a routed
    service is down."""
    routed_upstreams = set(ROUTE_TABLE.values())
    probed_upstreams = {client.base_url for client in _service_clients.values()}
    assert routed_upstreams <= probed_upstreams


def test_upstream_ws_url_keeps_port():
    assert _upstream_ws_url() == "ws://" + settings.RTO_URL.removeprefix("http://") + "/ws"


def test_unrouted_path_is_404():
    with TestClient(app) as client:
        response = client.get("/api/unknown")
    assert response.status_code == 404
