from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.passwords import hash_password, verify_password
from app.core.tokens import issue_token, read_token, require_buyer
from app.models.supplier import Supplier, SupplierAccount
from app.routers.suppliers import db_session, find_supplier
from app.services.buyers import authenticate_buyer, find_buyer, role_label

router = APIRouter(tags=["auth"])
MIN_PASSWORD = 8


class LoginRequest(BaseModel):
    username: str = Field(default="", max_length=80)
    password: str = Field(default="", max_length=200)


@router.get("/auth/status")
def auth_status() -> dict[str, bool]:
    return {"configured": get_settings().auth_ready()}


@router.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(db_session)) -> dict[str, str | int]:
    settings = get_settings()
    if not settings.auth_ready():
        raise AppError("auth_not_configured", "인증 설정이 없습니다.", 503)
    account = authenticate_buyer(db, body.username, body.password)
    stamp = password_stamp(account.password_set_at)
    token, expires_in = issue_token(
        settings,
        account.username,
        account.display_name,
        role=account.role,
        password_stamp=stamp,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "username": account.username,
        "name": account.display_name,
        "role": account.role,
        "roleLabel": role_label(account.role),
    }


class SupplierLoginRequest(BaseModel):
    code: str = Field(default="", max_length=20)
    password: str = Field(default="", max_length=200)


@router.post("/auth/supplier/login")
def supplier_login(body: SupplierLoginRequest, db: Session = Depends(db_session)) -> dict[str, str | int]:
    require_auth_configured()
    supplier = usable_supplier(db, body.code, for_login=True)
    account = supplier_account(db, supplier)
    if account is None or not account.password_hash or account.password_set_at is None:
        raise AppError("password_unset", "비밀번호를 설정하세요.", 409)
    if not verify_password(body.password.strip(), account.password_hash):
        raise AppError("unauthorized", "비밀번호가 올바르지 않습니다.", 401)
    return supplier_token(supplier, account)


@router.post("/auth/supplier/password")
def supplier_password(body: SupplierLoginRequest, db: Session = Depends(db_session)) -> dict[str, str | int]:
    require_auth_configured()
    supplier = usable_supplier(db, body.code, for_login=True)
    password = body.password.strip()
    if len(password) < MIN_PASSWORD:
        raise AppError("invalid_password", "비밀번호는 8자 이상으로 입력하세요.")
    account = supplier_account(db, supplier)
    if account is not None and account.password_hash and account.password_set_at is not None:
        raise AppError("password_already_set", "이미 비밀번호가 설정되어 있습니다.", 409)
    if account is None:
        account = SupplierAccount(supplier_id=supplier.id)
        db.add(account)
    account.password_hash = hash_password(password)
    account.password_set_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(account)
    return supplier_token(supplier, account)


@router.get("/auth/supplier/session")
def supplier_session(
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict[str, str]:
    identity = read_token(get_settings(), authorization)
    if identity.get("role") != "supplier":
        raise AppError("unauthorized", "로그인이 필요합니다.", 401)
    supplier = usable_supplier(db, identity["username"])
    account = supplier_account(db, supplier)
    stamp = password_stamp(account.password_set_at if account else None)
    if stamp is None or identity.get("pwd") != str(stamp):
        raise AppError("unauthorized", "로그인이 필요합니다.", 401)
    return {"username": supplier.code, "name": supplier.name, "role": "supplier"}


@router.get("/auth/me")
def me(
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict[str, str]:
    identity = require_buyer(authorization)
    if identity is None:
        raise AppError("auth_not_configured", "인증 설정이 없습니다.", 503)
    account = find_buyer(db, identity["username"])
    stamp = password_stamp(account.password_set_at)
    if stamp is None or identity.get("pwd") != str(stamp):
        raise AppError("unauthorized", "로그인이 필요합니다.", 401)
    if account.role != identity.get("role"):
        raise AppError("unauthorized", "로그인이 필요합니다.", 401)
    return {
        "username": account.username,
        "name": account.display_name,
        "role": account.role,
        "roleLabel": role_label(account.role),
    }


def require_auth_configured() -> None:
    if not get_settings().auth_ready():
        raise AppError("auth_not_configured", "인증 설정이 없습니다.", 503)


def usable_supplier(db: Session, code: str, *, for_login: bool = False) -> Supplier:
    try:
        supplier = find_supplier(db, code)
    except AppError as exc:
        if exc.code in ("not_found", "invalid_code"):
            if for_login:
                raise AppError(
                    "supplier_not_registered",
                    "업체등록이 되어 있지 않습니다. 구매사에 문의하세요.",
                    401,
                ) from exc
            raise AppError("unauthorized", "로그인이 필요합니다.", 401) from exc
        raise
    if supplier.use_status != "사용":
        raise AppError("supplier_stopped", "사용 중지된 협력사입니다. 구매사에 문의하세요.", 403)
    return supplier


def supplier_account(db: Session, supplier: Supplier) -> SupplierAccount | None:
    return db.scalar(select(SupplierAccount).where(SupplierAccount.supplier_id == supplier.id))


def password_stamp(value: datetime | None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())


def supplier_token(supplier: Supplier, account: SupplierAccount) -> dict[str, str | int]:
    settings = get_settings()
    if not settings.auth_ready():
        raise AppError("auth_not_configured", "인증 설정이 없습니다.", 503)
    stamp = password_stamp(account.password_set_at)
    token, expires_in = issue_token(
        settings,
        supplier.code,
        supplier.name,
        role="supplier",
        password_stamp=stamp,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "username": supplier.code,
        "name": supplier.name,
        "role": "supplier",
    }
