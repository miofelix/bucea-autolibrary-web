from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_runtime_settings_returns_real_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AUTO_LIBRARY_SECRET_KEY", "unit-test")
    monkeypatch.setenv("AUTO_LIBRARY_DATABASE_URL", f"sqlite:///{tmp_path}/s.db")
    monkeypatch.setenv("AUTO_LIBRARY_LOGIN_URL", "http://10.1.20.7/login")
    monkeypatch.setenv("ALLOW_LIVE_TEST", "true")
    monkeypatch.setenv("ALLOW_MUTATION_TEST", "false")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        response = client.get("/api/settings/runtime")

    assert response.status_code == 200
    body = response.json()
    assert body["library_login_url"] == "http://10.1.20.7/login"
    assert body["library_base_url"] == "http://10.1.20.7"
    assert body["allow_live_test"] is True
    assert body["allow_mutation_test"] is False
