import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.main import app
from app.routers.suppliers import db_session

SECRET = "test-secret-value-with-32-bytes!!"


def _reload_settings() -> None:
    get_settings.cache_clear()


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override():
        db = sessions()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[db_session] = override
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("AUTH_USERNAME", "gstec")
    monkeypatch.setenv("AUTH_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_DISPLAY_NAME", "지에스관리")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "30")
    _reload_settings()
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    _reload_settings()


def test_auth_status_needs_only_jwt(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    _reload_settings()
    response = TestClient(app).get("/auth/status")
    assert response.status_code == 200
    assert response.json() == {"configured": True}
    _reload_settings()


def test_auth_status_unconfigured(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "")
    _reload_settings()
    response = TestClient(app).get("/auth/status")
    assert response.status_code == 200
    assert response.json() == {"configured": False}
    _reload_settings()


def test_login_rejects_missing_jwt(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override():
        db = sessions()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[db_session] = override
    monkeypatch.setenv("JWT_SECRET", "")
    _reload_settings()
    response = TestClient(app).post("/auth/login", json={"username": "gstec", "password": "secret"})
    assert response.status_code == 503
    assert response.json()["code"] == "auth_not_configured"
    app.dependency_overrides.clear()
    _reload_settings()


def test_login_and_me(auth_client: TestClient) -> None:
    denied = auth_client.post("/auth/login", json={"username": "gstec", "password": "wrong"})
    assert denied.status_code == 401
    response = auth_client.post("/auth/login", json={"username": "gstec", "password": "secret-pass"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["name"] == "지에스관리"
    assert body["role"] == "admin"
    assert body["roleLabel"] == "관리자"
    payload = jwt.decode(body["access_token"], SECRET, algorithms=["HS256"])
    assert payload["sub"] == "gstec"
    assert payload["role"] == "admin"
    me = auth_client.get("/auth/me", headers={"Authorization": "Bearer " + body["access_token"]})
    assert me.status_code == 200
    assert me.json()["username"] == "gstec"
    assert me.json()["role"] == "admin"
    missing = auth_client.get("/auth/me")
    assert missing.status_code == 401


def test_approver_created_in_db(auth_client: TestClient) -> None:
    admin = auth_client.post("/auth/login", json={"username": "gstec", "password": "secret-pass"})
    headers = {"Authorization": "Bearer " + admin.json()["access_token"]}
    created = auth_client.post(
        "/buyers",
        headers=headers,
        json={"username": "approver", "name": "이승인", "role": "승인자", "password": "approve-pass"},
    )
    assert created.status_code == 201
    response = auth_client.post("/auth/login", json={"username": "approver", "password": "approve-pass"})
    assert response.status_code == 200
    assert response.json()["role"] == "approver"
    assert response.json()["roleLabel"] == "승인자"


def test_login_without_seed_reports_no_accounts(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override():
        db = sessions()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[db_session] = override
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    _reload_settings()
    response = TestClient(app).post("/auth/login", json={"username": "gstec", "password": "secret-pass"})
    assert response.status_code == 503
    assert response.json()["code"] == "no_accounts"
    app.dependency_overrides.clear()
    _reload_settings()


def test_shell_is_installable() -> None:
    client = TestClient(app)
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
