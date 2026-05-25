from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import ensure_sqlite_parent_dir
from app.main import create_app


def make_client(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTO_LIBRARY_SECRET_KEY", "test-secret")
    monkeypatch.setenv("AUTO_LIBRARY_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    get_settings.cache_clear()
    return TestClient(create_app())


def test_create_list_update_delete_user(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path) as client:
        create_response = client.post(
            "/api/users",
            json={
                "username": "student001",
                "password": "library-password",
                "display_name": "测试账号",
                "enabled": True,
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["username"] == "student001"
        assert "password" not in created
        assert "password_encrypted" not in created

        list_response = client.get("/api/users")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        update_response = client.put(
            f"/api/users/{created['id']}",
            json={"enabled": False, "password": "new-password"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["enabled"] is False
        assert "password" not in update_response.json()

        delete_response = client.delete(f"/api/users/{created['id']}")
        assert delete_response.status_code == 204

        list_response = client.get("/api/users")
        assert list_response.json() == []


def test_duplicate_username_returns_conflict(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path) as client:
        payload = {"username": "student001", "password": "library-password"}
        assert client.post("/api/users", json=payload).status_code == 201

        duplicate_response = client.post("/api/users", json=payload)

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["error"]["code"] == "conflict"


def test_sqlite_parent_directory_created(tmp_path):
    database_file = tmp_path / "nested" / "autolibrary.db"

    ensure_sqlite_parent_dir(f"sqlite:///{database_file}")

    assert database_file.parent.exists()
