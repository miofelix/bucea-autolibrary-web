from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_health_check(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTO_LIBRARY_SECRET_KEY", "test-secret")
    monkeypatch.setenv("AUTO_LIBRARY_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
