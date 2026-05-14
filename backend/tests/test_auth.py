from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def _client_with_auth_tokens(monkeypatch):
    monkeypatch.setenv("AUTH_USER_TOKENS", "student-001:test-token-1,student-002:test-token-2")
    get_settings.cache_clear()
    return TestClient(app)


def test_plan_requires_bearer_token(monkeypatch):
    client = _client_with_auth_tokens(monkeypatch)

    response = client.get("/api/v1/plan/course-1")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token."


def test_plan_allows_authenticated_owner(monkeypatch):
    client = _client_with_auth_tokens(monkeypatch)

    response = client.get(
        "/api/v1/plan/course-1",
        headers={"Authorization": "Bearer test-token-1"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Plan not found."
