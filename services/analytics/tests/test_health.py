from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "analytics-service"


def test_probe_endpoints_exist():
    with TestClient(app) as client:
        readiness = client.get("/readiness")
        liveness = client.get("/liveness")
    assert readiness.status_code in {200, 503}
    assert liveness.status_code == 200
