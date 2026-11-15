from fastapi.testclient import TestClient

from aegiscore import __version__
from aegiscore.main import app

client = TestClient(app)


def test_root_endpoint_returns_service_information():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "aegiscore-api",
        "message": "AegisCore AI API is running",
        "docs": "/docs",
    }


def test_health_endpoint_reports_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "aegiscore-api",
        "version": __version__,
    }


def test_openapi_schema_contains_system_endpoints():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "AegisCore AI API"
    assert "/health" in schema["paths"]
    assert "/" in schema["paths"]


def test_unknown_endpoint_returns_404():
    response = client.get("/this-route-does-not-exist")

    assert response.status_code == 404
