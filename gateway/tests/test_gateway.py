from fastapi.testclient import TestClient

from app.main import app
from app.proxy import resolve_upstream
from app.core.config import settings


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
    assert resolve_upstream("/api/reports/need-vs-fulfillment") == settings.ANALYTICS_URL
    assert resolve_upstream("/api/unknown") is None


def test_unrouted_path_is_404():
    with TestClient(app) as client:
        response = client.get("/api/unknown")
    assert response.status_code == 404
