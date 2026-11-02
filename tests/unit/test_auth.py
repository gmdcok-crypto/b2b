import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _reload_settings() -> None:
    get_settings.cache_clear()


def test_auth_status_unconfigured(monkeypatch, client) -> None:
    monkeypatch.setenv("JWT_SECRET", "")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    _reload_settings()
    response = client.get("/auth/status")
    assert response.status_code == 200
    assert response.json() == {"configured": False}
    _reload_settings()


def test_login_rejects_missing_configuration(monkeypatch, client) -> None:
    monkeypatch.setenv("JWT_SECRET", "")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    _reload_settings()
    response = client.post("/auth/login", json={"username": "buyer", "password": "secret"})
    assert response.status_code == 503
    assert response.json()["code"] == "auth_not_configured"
    _reload_settings()


def test_login_and_me(monkeypatch, client) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-secret-value-with-32-bytes!!")
    monkeypatch.setenv("AUTH_USERNAME", "buyer")
    monkeypatch.setenv("AUTH_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_DISPLAY_NAME", "김구매")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "30")
    _reload_settings()
    denied = client.post("/auth/login", json={"username": "buyer", "password": "wrong"})
    assert denied.status_code == 401
    response = client.post("/auth/login", json={"username": "buyer", "password": "secret-pass"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["name"] == "김구매"
    payload = jwt.decode(body["access_token"], "test-secret-value-with-32-bytes!!", algorithms=["HS256"])
    assert payload["sub"] == "buyer"
    me = client.get("/auth/me", headers={"Authorization": "Bearer " + body["access_token"]})
    assert me.status_code == 200
    assert me.json()["username"] == "buyer"
    missing = client.get("/auth/me")
    assert missing.status_code == 401
    _reload_settings()


def test_shell_is_installable(client) -> None:
    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    assert "manifest" in manifest.headers["content-type"]
    assert manifest.json()["display"] == "standalone"
    worker = client.get("/sw.js")
    assert worker.status_code == 200
    assert "/auth" in worker.text
    assert "/health" in worker.text
    icon = client.get("/icons/icon-192.png")
    assert icon.status_code == 200
    assert icon.headers["content-type"].startswith("image/png")
