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

    listed = supplier_client.get("/suppliers")
    assert listed.json()[0]["auth"] == "인증"

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
    cleared = supplier_client.get("/suppliers")
    assert cleared.json()[0]["auth"] == "미인증"

    stale = supplier_client.get("/auth/supplier/session", headers={"Authorization": "Bearer " + token})
    assert stale.status_code == 401

    after = supplier_client.post("/auth/supplier/login", json={"code": "V-0001", "password": "password1"})
    assert after.status_code == 409
    assert after.json()["code"] == "password_unset"

    renewed = supplier_client.post("/auth/supplier/password", json={"code": "V-0001", "password": "password2"})
    assert renewed.status_code == 200
    again = supplier_client.post("/auth/supplier/login", json={"code": "V-0001", "password": "password2"})
    assert again.status_code == 200


def test_password_set_requires_auth_configuration(monkeypatch: pytest.MonkeyPatch, supplier_client: TestClient) -> None:
    assert supplier_client.post("/suppliers", json={"code": "V-0003", "name": "설정대기"}).status_code == 201
    monkeypatch.setenv("JWT_SECRET", "")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    get_settings.cache_clear()
    denied = supplier_client.post("/auth/supplier/password", json={"code": "V-0003", "password": "password1"})
    assert denied.status_code == 503
    assert denied.json()["code"] == "auth_not_configured"
    listed = supplier_client.get("/suppliers").json()
    target = next(row for row in listed if row["code"] == "V-0003")
    assert target["auth"] == "미인증"
    get_settings.cache_clear()


def test_deleted_supplier_token_is_rejected(auth_env, supplier_client: TestClient) -> None:
    from sqlalchemy import select

    from app.models.supplier import Supplier, SupplierAccount
    from app.routers.suppliers import db_session as dependency

    assert supplier_client.post("/suppliers", json={"code": "V-0099", "name": "삭제대상"}).status_code == 201
    issued = supplier_client.post("/auth/supplier/password", json={"code": "V-0099", "password": "password1"})
    token = issued.json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    assert supplier_client.get("/auth/supplier/session", headers=headers).status_code == 200

    db_gen = supplier_client.app.dependency_overrides[dependency]()
    db = next(db_gen)
    try:
        row = db.scalar(select(Supplier).where(Supplier.code == "V-0099"))
        account = db.scalar(select(SupplierAccount).where(SupplierAccount.supplier_id == row.id))
        if account is not None:
            db.delete(account)
        db.delete(row)
        db.commit()
    finally:
        db_gen.close()

    assert supplier_client.get("/auth/supplier/session", headers=headers).status_code == 401
    assert supplier_client.get("/orders", headers=headers).status_code == 401
    missing = supplier_client.post("/auth/supplier/login", json={"code": "V-0099", "password": "password1"})
    assert missing.status_code == 401
    assert missing.json()["code"] == "supplier_not_registered"
    assert "업체등록" in missing.json()["message"]


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
