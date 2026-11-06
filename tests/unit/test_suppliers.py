import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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


def test_empty_database_lists_no_suppliers(supplier_client: TestClient) -> None:
    response = supplier_client.get("/suppliers")
    assert response.status_code == 200
    assert response.json() == []


def test_create_supplier_then_list_only_saved_row(supplier_client: TestClient) -> None:
    created = supplier_client.post(
        "/suppliers",
        json={"code": "v-new", "name": "새협력사", "bizNo": "1234567890", "contact": "김담당", "phone": "02-000-0000", "email": "a@example.com"},
    )
    assert created.status_code == 201
    assert created.json()["code"] == "V-NEW"
    assert created.json()["bizNo"] == "123-45-67890"
    assert created.json()["use"] == "사용"

    listed = supplier_client.get("/suppliers")
    assert [row["code"] for row in listed.json()] == ["V-NEW"]


def test_duplicate_supplier_code_is_rejected(supplier_client: TestClient) -> None:
    body = {"code": "V-NEW", "name": "새협력사"}
    assert supplier_client.post("/suppliers", json=body).status_code == 201
    again = supplier_client.post("/suppliers", json={"code": "V-NEW", "name": "다른상호"})
    assert again.status_code == 409
    assert again.json()["message"] == "이미 있는 협력사코드입니다."
