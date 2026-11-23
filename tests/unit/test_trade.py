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
def trade_client():
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


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("AUTH_USERNAME", "gstec")
    monkeypatch.setenv("AUTH_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_DISPLAY_NAME", "지에스관리")
    monkeypatch.setenv("AUTH_STAFF_USERNAME", "buyer")
    monkeypatch.setenv("AUTH_STAFF_PASSWORD", "secret-pass")
    monkeypatch.setenv("AUTH_STAFF_DISPLAY_NAME", "김구매")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def _ensure_approver(client: TestClient) -> dict[str, str]:
    admin = _login(client, "gstec", "secret-pass")
    created = client.post(
        "/buyers",
        headers=admin,
        json={"username": "approver", "name": "이승인", "role": "승인자", "password": "approve-pass"},
    )
    assert created.status_code == 201
    return _login(client, "approver", "approve-pass")


def _supplier_headers(client: TestClient, code: str = "V-0001") -> dict[str, str]:
    client.post("/auth/supplier/password", json={"code": code, "password": "password1"})
    token = client.post("/auth/supplier/login", json={"code": code, "password": "password1"}).json()["access_token"]
    return {"Authorization": "Bearer " + token}


def test_trade_lists_start_empty(trade_client: TestClient) -> None:
    assert trade_client.get("/items").json() == []
    assert trade_client.get("/prices").json() == []
    assert trade_client.get("/orders").json() == []
    assert trade_client.get("/audit").json() == []


def test_item_price_and_order_roundtrip(trade_client: TestClient) -> None:
    supplier = trade_client.post("/suppliers", json={"code": "V-0001", "name": "한빛금속"})
    assert supplier.status_code == 201

    created = trade_client.post(
        "/items",
        json={"code": "al-1", "name": "알루미늄", "spec": "Ø20", "unit": "M", "group": "원자재"},
    )
    assert created.status_code == 201
    assert created.json()["record"]["code"] == "AL-1"
    assert created.json()["record"]["use"] == "사용"
    assert created.json()["audit"]["action"] == "등록"

    stopped = trade_client.patch("/items/AL-1", json={"name": "알루미늄", "spec": "Ø20", "unit": "M", "group": "원자재", "use": "중지"})
    assert stopped.json()["record"]["use"] == "중지"
    resumed = trade_client.patch("/items/AL-1", json={"name": "알루미늄", "spec": "Ø20", "unit": "M", "group": "원자재", "use": "사용"})
    assert resumed.json()["audit"]["action"] == "사용재개"

    denied = trade_client.post(
        "/prices",
        json={"code": "AL-1", "vendor": "없는회사", "price": 1000, "from": "2026-11-01"},
    )
    assert denied.status_code == 400

    price = trade_client.post(
        "/prices",
        json={"code": "AL-1", "vendor": "한빛금속", "price": 4850, "from": "2026-11-01", "note": "계약"},
    )
    assert price.status_code == 201
    assert price.json()["record"]["id"].startswith("PR-")
    assert price.json()["record"]["status"] == "적용중"
    assert price.json()["record"]["history"][0]["type"] == "등록"
    price_id = price.json()["record"]["id"]

    requested = trade_client.post(
        "/prices/" + price_id + "/request",
        data={"request": "5000"},
        files={"file": ("공문.pdf", b"%PDF-1.4 test document", "application/pdf")},
    )
    assert requested.status_code == 200
    assert requested.json()["record"]["status"] == "승인대기"
    assert requested.json()["record"]["attachment"]["name"] == "공문.pdf"
    attachment_id = requested.json()["record"]["attachment"]["id"]
    downloaded = trade_client.get("/prices/" + price_id + "/attachments/" + str(attachment_id))
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF-1.4")
    reviewed = trade_client.post("/prices/" + price_id + "/decide", data={"type": "검토"})
    assert reviewed.json()["record"]["status"] == "검토완료"
    missing_file = trade_client.post("/prices/" + price_id + "/decide", data={"type": "승인"})
    assert missing_file.status_code == 400
    approved = trade_client.post(
        "/prices/" + price_id + "/decide",
        data={"type": "승인"},
        files={"file": ("결제.pdf", b"%PDF-1.4 approve", "application/pdf")},
    )
    assert approved.json()["record"]["price"] == 5000
    assert approved.json()["record"]["status"] == "적용중"
    approve_row = next(row for row in approved.json()["record"]["history"] if row["type"] == "승인")
    assert approve_row["attachment"]["name"] == "결제.pdf"
    assert "결제 공문" in approve_row["note"]

    peeked = trade_client.get("/orders/next-no")
    assert peeked.status_code == 200
    assert peeked.json()["id"].endswith("0001")
    order = trade_client.post(
        "/orders",
        json={
            "date": "2026-11-16",
            "due": "2026-11-20",
            "vendor": "한빛금속",
            "buyer": "김구매",
            "lines": [{"code": "AL-1", "name": "알루미늄", "spec": "Ø20", "unit": "M", "qty": 2, "price": 1, "due": "2026-12-01"}],
        },
    )
    assert order.status_code == 201
    assert order.json()["record"]["status"] == "작성"
    doc = order.json()["record"]["id"]
    assert doc == peeked.json()["id"]
    assert len(doc) == 10 and doc.isdigit()
    assert doc.endswith("0001")
    assert order.json()["record"]["due"] == "2026-11-20"
    assert order.json()["record"]["lines"][0]["due"] == "2026-11-20"
    assert order.json()["record"]["lines"][0]["price"] == 5000
    trade_client.post(
        "/items",
        json={"code": "NO-1", "name": "미계약", "unit": "EA", "group": "원자재"},
    )
    denied = trade_client.post(
        "/orders",
        json={
            "date": "2026-11-16",
            "due": "2026-11-20",
            "vendor": "한빛금속",
            "buyer": "김구매",
            "lines": [{"code": "NO-1", "qty": 1, "price": 100}],
        },
    )
    assert denied.status_code == 400
    second = trade_client.post(
        "/orders",
        json={
            "date": "2026-11-16",
            "due": "2026-11-20",
            "vendor": "한빛금속",
            "buyer": "김구매",
            "lines": [{"code": "AL-1", "name": "알루미늄", "spec": "Ø20", "unit": "M", "qty": 1, "price": 5000}],
        },
    )
    assert second.json()["record"]["id"] == doc[:6] + "0002"

    confirmed = trade_client.post(
        "/orders/" + doc + "/confirm",
        json={
            "date": "2026-11-16",
            "due": "2026-11-20",
            "vendor": "한빛금속",
            "buyer": "김구매",
            "lines": [{"code": "AL-1", "name": "알루미늄", "spec": "Ø20", "unit": "M", "qty": 2, "price": 5000}],
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["record"]["status"] == "확정"

    cancelled = trade_client.post("/orders/" + doc + "/cancel")
    assert cancelled.json()["record"]["status"] == "취소"
    actions = [row["action"] for row in trade_client.get("/audit").json()]
    assert "확정" in actions
    assert "취소" in actions
    assert "등록" in actions


def test_supplier_sees_only_own_confirmed_order(auth_env, trade_client: TestClient) -> None:
    buyer_headers = _login(trade_client, "buyer", "secret-pass")
    trade_client.post("/suppliers", headers=buyer_headers, json={"code": "V-0001", "name": "한빛금속"})
    trade_client.post("/suppliers", headers=buyer_headers, json={"code": "V-0002", "name": "세진"})
    created = trade_client.post(
        "/items",
        headers=buyer_headers,
        json={"code": "AL-1", "name": "알루미늄", "unit": "M", "group": "원자재"},
    )
    assert created.status_code == 201
    trade_client.post(
        "/prices",
        headers=buyer_headers,
        json={"code": "AL-1", "vendor": "한빛금속", "price": 10, "from": "2026-11-01"},
    )
    trade_client.post(
        "/prices",
        headers=buyer_headers,
        json={"code": "AL-1", "vendor": "세진", "price": 12, "from": "2026-11-01"},
    )
    trade_client.post("/auth/supplier/password", json={"code": "V-0001", "password": "password1"})
    token = trade_client.post("/auth/supplier/login", json={"code": "V-0001", "password": "password1"}).json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    payload = {"date": "2026-11-16", "due": "2026-11-20", "vendor": "한빛금속", "lines": [{"code": "AL-1", "qty": 1, "price": 999}]}

    draft = trade_client.post("/orders", headers=buyer_headers, json=payload)
    assert draft.status_code == 201
    assert draft.json()["record"]["lines"][0]["price"] == 10
    doc = draft.json()["record"]["id"]
    hidden = trade_client.get("/orders", headers=headers)
    assert hidden.status_code == 200
    assert hidden.json() == []

    trade_client.post("/orders/" + doc + "/confirm", headers=buyer_headers, json=payload)
    visible = trade_client.get("/orders", headers=headers).json()
    assert [row["id"] for row in visible] == [doc]
    other_payload = {"date": "2026-11-16", "due": "2026-11-20", "vendor": "세진", "lines": [{"code": "AL-1", "qty": 1, "price": 999}]}
    other = trade_client.post("/orders", headers=buyer_headers, json=other_payload)
    assert other.status_code == 201
    assert other.json()["record"]["lines"][0]["price"] == 12
    other_doc = other.json()["record"]["id"]
    trade_client.post("/orders/" + other_doc + "/confirm", headers=buyer_headers, json=other_payload)
    again = trade_client.get("/orders", headers=headers).json()
    assert [row["id"] for row in again] == [doc]
    items = trade_client.get("/items", headers=headers).json()
    assert [row["code"] for row in items] == ["AL-1"]


def test_price_review_and_approve_roles(auth_env, trade_client: TestClient) -> None:
    buyer = _login(trade_client, "buyer", "secret-pass")
    approver = _ensure_approver(trade_client)
    trade_client.post("/suppliers", headers=buyer, json={"code": "V-0001", "name": "한빛금속"})
    trade_client.post(
        "/items",
        headers=buyer,
        json={"code": "AL-1", "name": "알루미늄", "unit": "M", "group": "원자재"},
    )
    price = trade_client.post(
        "/prices",
        headers=buyer,
        json={"code": "AL-1", "vendor": "한빛금속", "price": 1000, "from": "2026-11-01"},
    )
    price_id = price.json()["record"]["id"]
    denied_buyer_request = trade_client.post(
        "/prices/" + price_id + "/request",
        headers=buyer,
        data={"request": "1200"},
        files={"file": ("공문.pdf", b"%PDF-1.4 x", "application/pdf")},
    )
    assert denied_buyer_request.status_code == 403
    supplier = _supplier_headers(trade_client)
    trade_client.post(
        "/prices/" + price_id + "/request",
        headers=supplier,
        data={"request": "1200"},
        files={"file": ("공문.pdf", b"%PDF-1.4 x", "application/pdf")},
    )
    denied = trade_client.post(
        "/prices/" + price_id + "/decide",
        headers=approver,
        data={"type": "승인"},
        files={"file": ("결제.pdf", b"%PDF-1.4 x", "application/pdf")},
    )
    assert denied.status_code == 400
    denied_review = trade_client.post("/prices/" + price_id + "/decide", headers=approver, data={"type": "검토"})
    assert denied_review.status_code == 403
    reviewed = trade_client.post("/prices/" + price_id + "/decide", headers=buyer, data={"type": "검토"})
    assert reviewed.json()["record"]["status"] == "검토완료"
    denied_staff = trade_client.post(
        "/prices/" + price_id + "/decide",
        headers=buyer,
        data={"type": "승인"},
        files={"file": ("결제.pdf", b"%PDF-1.4 x", "application/pdf")},
    )
    assert denied_staff.status_code == 403
    missing_file = trade_client.post("/prices/" + price_id + "/decide", headers=approver, data={"type": "승인"})
    assert missing_file.status_code == 400
    approved = trade_client.post(
        "/prices/" + price_id + "/decide",
        headers=approver,
        data={"type": "승인"},
        files={"file": ("결제.pdf", b"%PDF-1.4 x", "application/pdf")},
    )
    assert approved.json()["record"]["status"] == "적용중"
    assert approved.json()["record"]["price"] == 1200
    approve_row = next(row for row in approved.json()["record"]["history"] if row["type"] == "승인")
    assert approve_row["attachment"]["name"] == "결제.pdf"


def test_price_reject_keeps_before_and_after_same(auth_env, trade_client: TestClient) -> None:
    buyer = _login(trade_client, "buyer", "secret-pass")
    approver = _ensure_approver(trade_client)
    trade_client.post("/suppliers", headers=buyer, json={"code": "V-0001", "name": "한빛금속"})
    trade_client.post(
        "/items",
        headers=buyer,
        json={"code": "AL-1", "name": "알루미늄", "unit": "M", "group": "원자재"},
    )
    price = trade_client.post(
        "/prices",
        headers=buyer,
        json={"code": "AL-1", "vendor": "한빛금속", "price": 1000, "from": "2026-11-01"},
    )
    price_id = price.json()["record"]["id"]
    supplier = _supplier_headers(trade_client)
    trade_client.post(
        "/prices/" + price_id + "/request",
        headers=supplier,
        data={"request": "1500"},
        files={"file": ("공문.pdf", b"%PDF-1.4 x", "application/pdf")},
    )
    denied_staff = trade_client.post("/prices/" + price_id + "/decide", headers=buyer, data={"type": "반려"})
    assert denied_staff.status_code == 403
    reviewed = trade_client.post("/prices/" + price_id + "/decide", headers=buyer, data={"type": "검토"})
    assert reviewed.json()["record"]["status"] == "검토완료"
    rejected = trade_client.post("/prices/" + price_id + "/decide", headers=approver, data={"type": "반려"})
    assert rejected.status_code == 200
    record = rejected.json()["record"]
    assert record["status"] == "적용중"
    assert record["price"] == 1000
    assert record["request"] in (None, "", 0)
    reject_row = next(row for row in record["history"] if row["type"] == "반려")
    assert reject_row["before"] == 1000
    assert reject_row["after"] == 1000
    assert "1,500" in reject_row["note"]
