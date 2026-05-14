from fastapi.testclient import TestClient

from app.api import routes
from app.core.config import get_settings
from app.db.repository import RepositoryError
from app.main import app


def _client_with_auth_tokens(monkeypatch):
    monkeypatch.setenv("AUTH_USER_TOKENS", "student-001:test-token-1")
    get_settings.cache_clear()
    return TestClient(app)


def test_plan_returns_503_when_repository_load_fails(monkeypatch):
    client = _client_with_auth_tokens(monkeypatch)

    class _BrokenRepository:
        def get_roadmap(self, *args, **kwargs):
            raise RepositoryError("boom")

    app.dependency_overrides[routes.get_repository] = lambda: _BrokenRepository()

    try:
        response = client.get(
            "/api/v1/plan/course-1",
            headers={"Authorization": "Bearer test-token-1"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Unable to load roadmap."
