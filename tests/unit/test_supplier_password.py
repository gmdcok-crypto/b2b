import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.main import app
from app.routers.suppliers import db_session


@pytest.fixture
def supplier_client():
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
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


SECRET = "test-secret-value-with-32-bytes!!"


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("AUTH_USERNAME", "buyer")
    monkeypatch.setenv("AUTH_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_DISPLAY_NAME", "김구매")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_reset_clears_password_and_old_session(auth_env, supplier_client: TestClient) -> None:
    created = supplier_client.post("/suppliers", json={"code": "V-0001", "name": "한빛금속"})
    assert created.status_code == 201

    unset = supplier_client.post("/auth/supplier/login", json={"code": "V-0001", "password": "password1"})
    assert unset.status_code == 409
    assert unset.json()["code"] == "password_unset"

    short = supplier_client.post("/auth/supplier/password", json={"code": "V-0001", "password": "short"})
    assert short.status_code == 400

    first = supplier_client.post("/auth/supplier/password", json={"code": "V-0001", "password": "password1"})
    assert first.status_code == 200
    token = first.json()["access_token"]
    assert first.json()["username"] == "V-0001"

    session = supplier_client.get("/auth/supplier/session", headers={"Authorization": "Bearer " + token})
    assert session.status_code == 200
    assert session.json()["name"] == "한빛금속"

    duplicate = supplier_client.post("/auth/supplier/password", json={"code": "V-0001", "password": "password2"})
    assert duplicate.status_code == 409

    wrong = supplier_client.post("/auth/supplier/login", json={"code": "V-0001", "password": "nope-nope"})
    assert wrong.status_code == 401

    logged = supplier_client.post("/auth/supplier/login", json={"code": "V-0001", "password": "password1"})
    assert logged.status_code == 200

    buyer = supplier_client.post("/auth/login", json={"username": "buyer", "password": "secret-pass"})
    reset = supplier_client.post(
        "/suppliers/V-0001/password-reset",
        headers={"Authorization": "Bearer " + buyer.json()["access_token"]},
    )
    assert reset.status_code == 200
    assert reset.json() == {"code": "V-0001", "passwordSet": False}

    stale = supplier_client.get("/auth/supplier/session", headers={"Authorization": "Bearer " + token})
    assert stale.status_code == 401

    after = supplier_client.post("/auth/supplier/login", json={"code": "V-0001", "password": "password1"})
    assert after.status_code == 409
    assert after.json()["code"] == "password_unset"

    renewed = supplier_client.post("/auth/supplier/password", json={"code": "V-0001", "password": "password2"})
    assert renewed.status_code == 200
    again = supplier_client.post("/auth/supplier/login", json={"code": "V-0001", "password": "password2"})
    assert again.status_code == 200


def test_supplier_token_cannot_reset_password(auth_env, supplier_client: TestClient) -> None:
    assert supplier_client.post("/suppliers", json={"code": "V-0002", "name": "새협력사"}).status_code == 201
    issued = supplier_client.post("/auth/supplier/password", json={"code": "V-0002", "password": "password1"})
    supplier_token = issued.json()["access_token"]
    denied = supplier_client.post(
        "/suppliers/V-0002/password-reset",
        headers={"Authorization": "Bearer " + supplier_token},
    )
    assert denied.status_code == 403

    buyer = supplier_client.post("/auth/login", json={"username": "buyer", "password": "secret-pass"})
    allowed = supplier_client.post(
        "/suppliers/V-0002/password-reset",
        headers={"Authorization": "Bearer " + buyer.json()["access_token"]},
    )
    assert allowed.status_code == 200
