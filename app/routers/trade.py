"""품목, 계약 단가, 발주, 이력을 데이터베이스에 둔다."""

import re
from datetime import date, datetime

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tokens import require_buyer
from app.models.catalog import AuditLog, Item, Order, OrderLine, Price, PriceHistory
from app.models.supplier import Supplier
from app.routers.suppliers import db_session, find_supplier
from app.services.audit import actor_name, add_audit, audit_public, caller, money_text

router = APIRouter(tags=["trade"])
CODE_PATTERN = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")


class ItemBody(BaseModel):
    code: str = ""
    name: str = ""
    spec: str = ""
    unit: str = ""
    group: str = ""
    use: str = "사용"


class PriceBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str = ""
    vendor: str = ""
    price: int = 0
    starts: str = Field(default="", validation_alias="from")
    to: str = ""
    note: str = ""


class PriceRequestBody(BaseModel):
    request: int = 0


class PriceDecideBody(BaseModel):
    type: str = ""


class LineBody(BaseModel):
    code: str = ""
    name: str = ""
    spec: str = ""
    unit: str = ""
    qty: float = 0
    price: int = 0
    due: str = ""


class OrderBody(BaseModel):
    date: str = ""
    due: str = ""
    vendor: str = ""
    buyer: str = ""
    currency: str = "KRW"
    vat: str = "별도"
    note: str = ""
    lines: list[LineBody] = []


def scoped_supplier(db: Session, authorization: str | None) -> Supplier | None:
    identity = caller(authorization)
    if identity is None:
        return None
    if identity.get("role") != "supplier":
        return None
    try:
        supplier = find_supplier(db, identity["username"])
    except AppError as exc:
        if exc.code == "not_found":
            raise AppError("unauthorized", "로그인이 필요합니다.", 401) from exc
        raise
    if supplier.use_status != "사용":
        raise AppError("supplier_stopped", "사용 중지된 협력사입니다.", 403)
    return supplier


def require_trade_buyer(authorization: str | None) -> str:
    require_buyer(authorization)
    return actor_name(authorization)


def clean_code(value: str) -> str:
    code = value.strip().upper()
    if not code or len(code) > 20 or not CODE_PATTERN.fullmatch(code):
        raise AppError("invalid_code", "코드는 영문 대문자, 숫자, 하이픈만 20자 이내로 입력하세요.")
    return code


def clean_use(value: str) -> str:
    if value not in ("사용", "중지"):
        raise AppError("invalid_use", "사용 여부는 사용 또는 중지입니다.")
    return value


def parse_day(value: str, label: str, *, required: bool) -> date | None:
    text = (value or "").strip()
    if not text:
        if required:
            raise AppError("invalid_date", label + "을 입력하세요.")
        return None
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise AppError("invalid_date", label + "을 입력하세요.") from exc
    if parsed.isoformat() != text:
        raise AppError("invalid_date", label + "을 입력하세요.")
    return parsed


def active_supplier(db: Session, name: str) -> Supplier:
    vendor = name.strip()
    row = db.scalar(select(Supplier).where(Supplier.name == vendor, Supplier.use_status == "사용"))
    if row is None:
        raise AppError("invalid_vendor", "사용 중인 협력사를 선택하세요.")
    return row


def find_item(db: Session, code: str) -> Item:
    row = db.scalar(select(Item).where(Item.code == clean_code(code)))
    if row is None:
        raise AppError("not_found", "품목을 찾을 수 없습니다.", 404)
    return row


def find_price(db: Session, doc_no: str) -> Price:
    row = db.scalar(select(Price).where(Price.doc_no == doc_no.strip()))
    if row is None:
        raise AppError("not_found", "계약단가를 찾을 수 없습니다.", 404)
    return row


def find_order(db: Session, doc_no: str) -> Order:
    row = db.scalar(select(Order).where(Order.doc_no == doc_no.strip()))
    if row is None:
        raise AppError("not_found", "발주를 찾을 수 없습니다.", 404)
    return row


def supplier_map(db: Session) -> dict[int, Supplier]:
    return {row.id: row for row in db.scalars(select(Supplier)).all()}


def item_map(db: Session) -> dict[int, Item]:
    return {row.id: row for row in db.scalars(select(Item)).all()}


def item_public(row: Item) -> dict[str, str]:
    return {
        "code": row.code,
        "name": row.name,
        "spec": row.spec or "",
        "unit": row.unit,
        "group": row.group_name,
        "use": row.use_status,
    }


def history_public(rows: list[PriceHistory]) -> list[dict[str, str | int]]:
    ordered = sorted(rows, key=lambda row: row.id, reverse=True)
    return [
        {
            "date": row.entry_date.isoformat(),
            "type": row.entry_type,
            "before": "" if row.before_amount is None else row.before_amount,
            "after": "" if row.after_amount is None else row.after_amount,
            "by": row.actor,
            "note": row.note or "",
        }
        for row in ordered
    ]


def price_public(row: Price, item: Item, supplier: Supplier, histories: list[PriceHistory]) -> dict:
    return {
        "id": row.doc_no,
        "code": item.code,
        "name": item.name,
        "spec": item.spec or "",
        "unit": item.unit,
        "vendor": supplier.name,
        "price": row.amount,
        "request": "" if row.request_amount is None else row.request_amount,
        "from": row.valid_from.isoformat(),
        "to": "" if row.valid_to is None else row.valid_to.isoformat(),
        "note": row.note or "",
        "status": row.status,
        "history": history_public(histories),
    }


def line_public(row: OrderLine) -> dict:
    qty = row.qty
    if float(qty).is_integer():
        qty = int(qty)
    return {
        "code": row.item_code or "",
        "name": row.name or "",
        "spec": row.spec or "",
        "unit": row.unit or "",
        "qty": qty,
        "price": row.unit_price,
        "due": "" if row.due_date is None else row.due_date.isoformat(),
    }


def order_public(row: Order, supplier: Supplier, lines: list[OrderLine]) -> dict:
    ordered = sorted(lines, key=lambda line: line.line_no)
    return {
        "id": row.doc_no,
        "date": row.order_date.isoformat(),
        "due": row.due_date.isoformat(),
        "vendor": supplier.name,
        "buyer": row.buyer or "",
        "status": row.status,
        "currency": row.currency or "KRW",
        "vat": row.vat or "별도",
        "note": row.note or "",
        "lines": [line_public(line) for line in ordered],
    }


def lines_for(db: Session, order_ids: list[int]) -> dict[int, list[OrderLine]]:
    grouped: dict[int, list[OrderLine]] = {order_id: [] for order_id in order_ids}
    if not order_ids:
        return grouped
    rows = db.scalars(select(OrderLine).where(OrderLine.order_id.in_(order_ids))).all()
    for row in rows:
        grouped.setdefault(row.order_id, []).append(row)
    return grouped


def histories_for(db: Session, price_ids: list[int]) -> dict[int, list[PriceHistory]]:
    grouped: dict[int, list[PriceHistory]] = {price_id: [] for price_id in price_ids}
    if not price_ids:
        return grouped
    rows = db.scalars(select(PriceHistory).where(PriceHistory.price_id.in_(price_ids))).all()
    for row in rows:
        grouped.setdefault(row.price_id, []).append(row)
    return grouped


def traded_codes(db: Session, supplier: Supplier) -> set[str]:
    codes: set[str] = set()
    orders = db.scalars(
        select(Order).where(Order.supplier_id == supplier.id, Order.status != "작성")
    ).all()
    grouped = lines_for(db, [row.id for row in orders])
    for lines in grouped.values():
        for line in lines:
            if line.item_code:
                codes.add(line.item_code)
    prices = db.scalars(select(Price).where(Price.supplier_id == supplier.id)).all()
    items = item_map(db)
    for price in prices:
        item = items.get(price.item_id)
        if item is not None:
            codes.add(item.code)
    return codes


def envelope(record: dict, audit: AuditLog) -> dict:
    return {"record": record, "audit": audit_public(audit)}


def apply_item(row: Item, body: ItemBody, *, code: str | None) -> None:
    name = body.name.strip()
    if not name or len(name) > 100:
        raise AppError("invalid_name", "품명을 입력하세요.")
    unit = body.unit.strip()
    group = body.group.strip()
    if not unit or len(unit) > 10:
        raise AppError("invalid_unit", "단위를 선택하세요.")
    if not group or len(group) > 20:
        raise AppError("invalid_group", "분류를 선택하세요.")
    row.name = name
    row.spec = body.spec.strip()[:120]
    row.unit = unit
    row.group_name = group
    row.use_status = clean_use(body.use or "사용")
    if code is not None:
        row.code = code


def replace_lines(db: Session, order: Order, lines: list[LineBody]) -> None:
    existing = db.scalars(select(OrderLine).where(OrderLine.order_id == order.id)).all()
    for row in existing:
        db.delete(row)
    number = 1
    for line in lines:
        code = line.code.strip().upper()
        if not code and not line.name.strip() and not line.qty:
            continue
        due = parse_day(line.due, "납기", required=False)
        db.add(
            OrderLine(
                order_id=order.id,
                line_no=number,
                item_code=code[:20],
                name=line.name.strip()[:100],
                spec=line.spec.strip()[:120],
                unit=line.unit.strip()[:10],
                qty=float(line.qty or 0),
                unit_price=int(line.price or 0),
                due_date=due,
            )
        )
        number += 1


def apply_order(db: Session, row: Order, body: OrderBody) -> Supplier:
    supplier = active_supplier(db, body.vendor)
    start = parse_day(body.date, "발주일", required=True)
    due = parse_day(body.due, "납기일", required=True)
    assert start is not None and due is not None
    row.order_date = start
    row.due_date = due
    row.supplier_id = supplier.id
    row.buyer = (body.buyer or "김구매").strip()[:50]
    row.currency = (body.currency or "KRW").strip()[:10] or "KRW"
    row.vat = (body.vat or "별도").strip()[:10] or "별도"
    row.note = body.note.strip()[:200]
    return supplier


def next_order_no(db: Session) -> str:
    today = date.today()
    prefix = "PO-" + today.strftime("%Y%m") + "-"
    rows = db.scalars(select(Order.doc_no).where(Order.doc_no.like(prefix + "%"))).all()
    seq = 0
    for doc in rows:
        tail = doc.rsplit("-", 1)[-1]
        if tail.isdigit():
            seq = max(seq, int(tail))
    return prefix + f"{seq + 1:04d}"


def next_price_no(db: Session) -> str:
    rows = db.scalars(select(Price.doc_no)).all()
    seq = 0
    for doc in rows:
        digits = "".join(character for character in doc if character.isdigit())
        if digits:
            seq = max(seq, int(digits))
    return "PR-" + str(seq + 1)


def add_history(
    db: Session,
    price: Price,
    *,
    entry_type: str,
    before: int | None,
    after: int | None,
    actor: str,
    note: str = "",
) -> None:
    db.add(
        PriceHistory(
            price_id=price.id,
            entry_date=date.today(),
            entry_type=entry_type,
            before_amount=before,
            after_amount=after,
            actor=actor[:100],
            note=note.strip()[:200],
        )
    )


def published_order(db: Session, row: Order) -> dict:
    supplier = supplier_map(db)[row.supplier_id]
    lines = lines_for(db, [row.id]).get(row.id, [])
    return order_public(row, supplier, lines)


def published_price(db: Session, row: Price) -> dict:
    item = item_map(db)[row.item_id]
    supplier = supplier_map(db)[row.supplier_id]
    histories = histories_for(db, [row.id]).get(row.id, [])
    return price_public(row, item, supplier, histories)


@router.get("/items")
def list_items(
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> list[dict[str, str]]:
    scope = scoped_supplier(db, authorization)
    rows = db.scalars(select(Item).order_by(Item.code)).all()
    if scope is not None:
        codes = traded_codes(db, scope)
        rows = [row for row in rows if row.code in codes]
    return [item_public(row) for row in rows]


@router.post("/items", status_code=201)
def create_item(
    body: ItemBody,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict:
    user = require_trade_buyer(authorization)
    code = clean_code(body.code)
    if db.scalar(select(Item).where(Item.code == code)) is not None:
        raise AppError("duplicate_code", "이미 있는 품목코드입니다.", 409)
    row = Item(code=code, name="", spec="", unit="EA", group_name="원자재", use_status="사용")
    apply_item(row, body, code=code)
    db.add(row)
    audit = add_audit(db, user=user, action="등록", target=row.code, after=row.name, note=row.spec)
    db.commit()
    db.refresh(row)
    db.refresh(audit)
    return envelope(item_public(row), audit)


@router.patch("/items/{code}")
def update_item(
    code: str,
    body: ItemBody,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict:
    user = require_trade_buyer(authorization)
    row = find_item(db, code)
    before_use = row.use_status
    apply_item(row, body, code=None)
    if before_use != row.use_status:
        action = "사용중지" if row.use_status == "중지" else "사용재개"
        audit = add_audit(db, user=user, action=action, target=row.code, before=before_use, after=row.use_status)
    else:
        audit = add_audit(db, user=user, action="수정", target=row.code, after=row.name, note=row.spec)
    db.commit()
    db.refresh(row)
    db.refresh(audit)
    return envelope(item_public(row), audit)


@router.get("/prices")
def list_prices(
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> list[dict]:
    scope = scoped_supplier(db, authorization)
    rows = db.scalars(select(Price).order_by(Price.doc_no)).all()
    if scope is not None:
        rows = [row for row in rows if row.supplier_id == scope.id]
    items = item_map(db)
    suppliers = supplier_map(db)
    histories = histories_for(db, [row.id for row in rows])
    return [
        price_public(row, items[row.item_id], suppliers[row.supplier_id], histories.get(row.id, []))
        for row in rows
        if row.item_id in items and row.supplier_id in suppliers
    ]


@router.post("/prices", status_code=201)
def create_price(
    body: PriceBody,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict:
    user = require_trade_buyer(authorization)
    item = find_item(db, body.code)
    if item.use_status != "사용":
        raise AppError("item_stopped", "사용 중인 품목만 계약단가를 등록할 수 있습니다.")
    supplier = active_supplier(db, body.vendor)
    if body.price <= 0:
        raise AppError("invalid_price", "계약단가는 1원 이상의 정수로 입력하세요.")
    start = parse_day(body.starts, "적용시작일", required=True)
    end = parse_day(body.to, "적용종료일", required=False)
    assert start is not None
    if end is not None and end < start:
        raise AppError("invalid_date", "적용종료일은 적용시작일 이후로 입력하세요.")
    row = Price(
        doc_no=next_price_no(db),
        item_id=item.id,
        supplier_id=supplier.id,
        amount=int(body.price),
        request_amount=None,
        valid_from=start,
        valid_to=end,
        note=body.note.strip()[:200],
        status="적용중",
    )
    db.add(row)
    db.flush()
    add_history(db, row, entry_type="등록", before=None, after=row.amount, actor=user, note=row.note)
    audit = add_audit(
        db,
        user=user,
        action="등록",
        target=item.code,
        after=money_text(row.amount),
        note=supplier.name,
    )
    db.commit()
    db.refresh(row)
    db.refresh(audit)
    return envelope(published_price(db, row), audit)


@router.post("/prices/{doc_no}/request")
def request_price(
    doc_no: str,
    body: PriceRequestBody,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict:
    identity = caller(authorization)
    row = find_price(db, doc_no)
    supplier = supplier_map(db)[row.supplier_id]
    if identity is not None and identity.get("role") == "supplier":
        if identity["username"].upper() != supplier.code.upper():
            raise AppError("forbidden", "자사 단가만 요청할 수 있습니다.", 403)
        user = supplier.name
    else:
        user = require_trade_buyer(authorization)
    if row.status != "적용중":
        raise AppError("invalid_status", "적용 중인 단가만 변경 요청할 수 있습니다.")
    if body.request <= 0 or body.request == row.amount:
        raise AppError("invalid_price", "현재단가와 다른 요청단가를 입력하세요.")
    row.request_amount = int(body.request)
    row.status = "승인대기"
    add_history(db, row, entry_type="변경요청", before=row.amount, after=row.request_amount, actor=user)
    audit = add_audit(
        db,
        user=user,
        action="변경요청",
        target=item_map(db)[row.item_id].code,
        before=money_text(row.amount),
        after=money_text(row.request_amount),
    )
    db.commit()
    db.refresh(row)
    db.refresh(audit)
    return envelope(published_price(db, row), audit)


@router.post("/prices/{doc_no}/decide")
def decide_price(
    doc_no: str,
    body: PriceDecideBody,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict:
    user = require_trade_buyer(authorization)
    row = find_price(db, doc_no)
    if row.status != "승인대기" or row.request_amount is None:
        raise AppError("invalid_status", "승인 대기 중인 단가가 없습니다.")
    if body.type not in ("승인", "반려"):
        raise AppError("invalid_status", "승인 또는 반려만 처리할 수 있습니다.")
    before = row.amount
    after = row.request_amount
    if body.type == "승인":
        row.amount = after
    row.request_amount = None
    row.status = "적용중"
    add_history(db, row, entry_type=body.type, before=before, after=after, actor=user)
    audit = add_audit(
        db,
        user=user,
        action=body.type,
        target=item_map(db)[row.item_id].code,
        before=money_text(before),
        after=money_text(after),
    )
    db.commit()
    db.refresh(row)
    db.refresh(audit)
    return envelope(published_price(db, row), audit)


@router.get("/orders")
def list_orders(
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> list[dict]:
    scope = scoped_supplier(db, authorization)
    rows = db.scalars(select(Order).order_by(Order.doc_no.desc())).all()
    if scope is not None:
        rows = [row for row in rows if row.supplier_id == scope.id and row.status != "작성"]
    suppliers = supplier_map(db)
    grouped = lines_for(db, [row.id for row in rows])
    return [
        order_public(row, suppliers[row.supplier_id], grouped.get(row.id, []))
        for row in rows
        if row.supplier_id in suppliers
    ]


@router.post("/orders", status_code=201)
def create_order(
    body: OrderBody,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict:
    require_trade_buyer(authorization)
    row = Order(
        doc_no=next_order_no(db),
        order_date=date.today(),
        due_date=date.today(),
        supplier_id=0,
        buyer="",
        status="작성",
        currency="KRW",
        vat="별도",
        note="",
    )
    supplier = apply_order(db, row, body)
    db.add(row)
    db.flush()
    replace_lines(db, row, body.lines)
    db.commit()
    db.refresh(row)
    return {"record": published_order(db, row), "audit": None, "vendorId": supplier.id}


@router.patch("/orders/{doc_no}")
def update_order(
    doc_no: str,
    body: OrderBody,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict:
    require_trade_buyer(authorization)
    row = find_order(db, doc_no)
    if row.status != "작성":
        raise AppError("invalid_status", "작성 중인 발주만 저장할 수 있습니다.")
    apply_order(db, row, body)
    replace_lines(db, row, body.lines)
    db.commit()
    db.refresh(row)
    return {"record": published_order(db, row), "audit": None}


@router.post("/orders/{doc_no}/confirm")
def confirm_order(
    doc_no: str,
    body: OrderBody,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict:
    user = require_trade_buyer(authorization)
    row = find_order(db, doc_no)
    if row.status != "작성":
        raise AppError("invalid_status", "작성 중인 발주만 확정할 수 있습니다.")
    apply_order(db, row, body)
    replace_lines(db, row, body.lines)
    db.flush()
    lines = db.scalars(select(OrderLine).where(OrderLine.order_id == row.id)).all()
    if not any(line.item_code and line.qty and line.qty > 0 for line in lines):
        raise AppError("invalid_lines", "품목코드와 수량이 있는 행이 없습니다.")
    row.status = "확정"
    audit = add_audit(db, user=user, action="확정", target=row.doc_no, before="작성", after="확정")
    db.commit()
    db.refresh(row)
    db.refresh(audit)
    return envelope(published_order(db, row), audit)


@router.post("/orders/{doc_no}/cancel")
def cancel_order(
    doc_no: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict:
    user = require_trade_buyer(authorization)
    row = find_order(db, doc_no)
    if row.status != "확정":
        raise AppError("invalid_status", "확정된 발주만 취소할 수 있습니다.")
    row.status = "취소"
    audit = add_audit(db, user=user, action="취소", target=row.doc_no, before="확정", after="취소")
    db.commit()
    db.refresh(row)
    db.refresh(audit)
    return envelope(published_order(db, row), audit)


@router.get("/audit")
def list_audit(
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> list[dict[str, str]]:
    scope = scoped_supplier(db, authorization)
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc())).all()
    if scope is None:
        return [audit_public(row) for row in rows]
    order_ids = [
        row.doc_no
        for row in db.scalars(select(Order).where(Order.supplier_id == scope.id, Order.status != "작성")).all()
    ]
    codes = traded_codes(db, scope)
    visible = []
    for row in rows:
        if row.user_name == scope.name or row.target in order_ids or row.target in codes:
            visible.append(audit_public(row))
    return visible
