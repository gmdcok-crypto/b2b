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


@pytest.fixture
def buyer_client(monkeypatch: pytest.MonkeyPatch):
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
    monkeypatch.setenv("AUTH_USERNAME", "buyer")
    monkeypatch.setenv("AUTH_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_DISPLAY_NAME", "김구매")
    monkeypatch.setenv("AUTH_APPROVER_USERNAME", "approver")
    monkeypatch.setenv("AUTH_APPROVER_PASSWORD", "approve-pass")
    monkeypatch.setenv("AUTH_APPROVER_DISPLAY_NAME", "이승인")
    get_settings.cache_clear()
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_list_seeded_buyers(buyer_client: TestClient) -> None:
    headers = _login(buyer_client, "buyer", "secret-pass")
    rows = buyer_client.get("/buyers", headers=headers).json()
    assert {row["username"] for row in rows} == {"buyer", "approver"}
    assert {row["role"] for row in rows} == {"담당", "승인자"}


def test_create_and_login_new_buyer(buyer_client: TestClient) -> None:
    headers = _login(buyer_client, "buyer", "secret-pass")
    created = buyer_client.post(
        "/buyers",
        headers=headers,
        json={"username": "staff2", "name": "박담당", "role": "담당", "use": "사용", "password": "password1"},
    )
    assert created.status_code == 201
    assert created.json()["record"]["name"] == "박담당"
    login = buyer_client.post("/auth/login", json={"username": "staff2", "password": "password1"})
    assert login.status_code == 200
    assert login.json()["role"] == "buyer"


def test_cannot_stop_last_approver(buyer_client: TestClient) -> None:
    headers = _login(buyer_client, "buyer", "secret-pass")
    denied = buyer_client.patch(
        "/buyers/approver",
        headers=headers,
        json={"username": "approver", "name": "이승인", "role": "승인자", "use": "중지", "password": ""},
    )
    assert denied.status_code == 400
    assert denied.json()["code"] == "invalid_role"


def test_change_password_and_role(buyer_client: TestClient) -> None:
    headers = _login(buyer_client, "approver", "approve-pass")
    buyer_client.post(
        "/buyers",
        headers=headers,
        json={"username": "boss2", "name": "최승인", "role": "승인자", "password": "password1"},
    )
    changed = buyer_client.post(
        "/buyers/boss2/password",
        headers=headers,
        json={"password": "password2"},
    )
    assert changed.status_code == 200
    assert buyer_client.post("/auth/login", json={"username": "boss2", "password": "password1"}).status_code == 401
    assert buyer_client.post("/auth/login", json={"username": "boss2", "password": "password2"}).status_code == 200
    updated = buyer_client.patch(
        "/buyers/boss2",
        headers=headers,
        json={"username": "boss2", "name": "최승인", "role": "담당", "use": "사용", "password": ""},
    )
    assert updated.status_code == 200
    assert updated.json()["record"]["role"] == "담당"


def test_env_password_does_not_overwrite_managed_password(buyer_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _login(buyer_client, "buyer", "secret-pass")
    buyer_client.post(
        "/buyers/buyer/password",
        headers=headers,
        json={"password": "changed-pass"},
    )
    monkeypatch.setenv("AUTH_PASSWORD", "secret-pass")
    get_settings.cache_clear()
    assert buyer_client.post("/auth/login", json={"username": "buyer", "password": "secret-pass"}).status_code == 401
    again = buyer_client.post("/auth/login", json={"username": "buyer", "password": "changed-pass"})
    assert again.status_code == 200
