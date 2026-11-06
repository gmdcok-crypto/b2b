from collections.abc import Generator
import re

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tokens import require_buyer
from app.db.session import get_db
from app.models.supplier import Supplier, SupplierAccount

router = APIRouter(tags=["suppliers"])
CODE_PATTERN = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class SupplierBody(BaseModel):
    code: str = ""
    name: str = ""
    bizNo: str = ""
    contact: str = ""
    phone: str = ""
    email: str = ""
    use: str = "사용"


def db_session() -> Generator[Session, None, None]:
    try:
        yield from get_db()
    except RuntimeError as exc:
        raise AppError("database_not_configured", "데이터베이스가 연결되지 않았습니다.", 503) from exc


def to_public(row: Supplier) -> dict[str, str]:
    return {
        "code": row.code,
        "name": row.name,
        "bizNo": row.biz_no or "",
        "contact": row.contact or "",
        "phone": row.phone or "",
        "email": row.email or "",
        "use": row.use_status,
    }


def clean_code(value: str) -> str:
    code = value.strip().upper()
    if not code or len(code) > 20 or not CODE_PATTERN.fullmatch(code):
        raise AppError("invalid_code", "협력사코드는 영문 대문자, 숫자, 하이픈만 20자 이내로 입력하세요.")
    return code


def clean_name(value: str) -> str:
    name = value.strip()
    if not name or len(name) > 100:
        raise AppError("invalid_name", "협력사명을 입력하세요.")
    return name


def clean_biz_no(value: str) -> str | None:
    digits = "".join(character for character in value if character.isdigit())
    if not digits:
        return None
    if len(digits) != 10:
        raise AppError("invalid_biz_no", "사업자번호는 10자리 숫자로 입력하세요.")
    return digits[:3] + "-" + digits[3:5] + "-" + digits[5:]


def clean_use(value: str) -> str:
    if value not in ("사용", "중지"):
        raise AppError("invalid_use", "사용 여부는 사용 또는 중지입니다.")
    return value


def clean_email(value: str) -> str:
    email = value.strip()
    if email and (len(email) > 120 or not EMAIL_PATTERN.fullmatch(email)):
        raise AppError("invalid_email", "이메일 형식을 확인하세요.")
    return email


def apply_fields(row: Supplier, body: SupplierBody, *, code: str | None) -> None:
    row.name = clean_name(body.name)
    row.biz_no = clean_biz_no(body.bizNo)
    row.contact = body.contact.strip()[:50]
    row.phone = body.phone.strip()[:30]
    row.email = clean_email(body.email)
    row.use_status = clean_use(body.use or "사용")
    if code is not None:
        row.code = code


@router.get("/suppliers")
def list_suppliers(db: Session = Depends(db_session)) -> list[dict[str, str]]:
    rows = db.scalars(select(Supplier).order_by(Supplier.code)).all()
    return [to_public(row) for row in rows]


@router.post("/suppliers", status_code=201)
def create_supplier(body: SupplierBody, db: Session = Depends(db_session)) -> dict[str, str]:
    row = Supplier(code="", name="", use_status="사용")
    apply_fields(row, body, code=clean_code(body.code))
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise duplicate_error(exc) from exc
    db.refresh(row)
    return to_public(row)


@router.patch("/suppliers/{code}")
def update_supplier(code: str, body: SupplierBody, db: Session = Depends(db_session)) -> dict[str, str]:
    row = find_supplier(db, code)
    apply_fields(row, body, code=None)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise duplicate_error(exc) from exc
    db.refresh(row)
    return to_public(row)


@router.post("/suppliers/{code}/password-reset")
def reset_supplier_password(
    code: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict[str, str | bool]:
    require_buyer(authorization)
    supplier = find_supplier(db, code)
    account = db.scalar(select(SupplierAccount).where(SupplierAccount.supplier_id == supplier.id))
    if account is None:
        account = SupplierAccount(supplier_id=supplier.id)
        db.add(account)
    account.password_hash = None
    account.password_set_at = None
    db.commit()
    return {"code": supplier.code, "passwordSet": False}


def find_supplier(db: Session, code: str) -> Supplier:
    row = db.scalar(select(Supplier).where(Supplier.code == clean_code(code)))
    if row is None:
        raise AppError("not_found", "협력사를 찾을 수 없습니다.", 404)
    return row


def duplicate_error(exc: IntegrityError) -> AppError:
    text = str(exc.orig).lower()
    if "biz_no" in text:
        return AppError("duplicate_biz_no", "이미 있는 사업자번호입니다.", 409)
    if "suppliers.name" in text or "uq_suppliers_name" in text:
        return AppError("duplicate_name", "이미 있는 협력사명입니다.", 409)
    if "suppliers.code" in text or "uq_suppliers_code" in text:
        return AppError("duplicate_code", "이미 있는 협력사코드입니다.", 409)
    return AppError("save_failed", "협력사를 저장하지 못했습니다.", 409)
