import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def stub_process(monkeypatch, payload=None):
    payload = payload or {"status": "CLEAR", "data": [], "attempts_used": 1}
    monkeypatch.setattr("app.main.process_query", lambda prompt: payload)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "connected"


def test_query_endpoint(client, monkeypatch):
    stub_process(monkeypatch)
    response = client.post("/api/v1/query", json={"prompt": "Show revenue"})
    assert response.status_code == 200
    assert response.json()["status"] == "CLEAR"


def test_request_validation(client):
    assert client.post("/api/v1/query", json={"prompt": ""}).status_code == 422
    assert client.post("/api/v1/query", json={}).status_code == 422


def test_api_key_is_required_when_configured(client, monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "test-secret")
    stub_process(monkeypatch)

    assert client.post("/api/v1/query", json={"prompt": "hi"}).status_code == 401
    assert (
        client.post(
            "/api/v1/query",
            json={"prompt": "hi"},
            headers={"X-API-Key": "wrong"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/query",
            json={"prompt": "hi"},
            headers={"X-API-Key": "test-secret"},
        ).status_code
        == 200
    )


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 2)
    stub_process(monkeypatch)

    assert client.post("/api/v1/query", json={"prompt": "hi"}).status_code == 200
    assert client.post("/api/v1/query", json={"prompt": "hi"}).status_code == 200
    assert client.post("/api/v1/query", json={"prompt": "hi"}).status_code == 429


def test_unexpected_error_does_not_leak_internals(client, monkeypatch):
    def explode(prompt):
        raise RuntimeError("super secret connection string")

    monkeypatch.setattr("app.main.process_query", explode)

    response = client.post("/api/v1/query", json={"prompt": "hi"})

    assert response.status_code == 500
    assert "Reference:" in response.json()["detail"]
    assert "super secret" not in response.text
