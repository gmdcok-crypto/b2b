"""구매 담당·승인자 계정 관리."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.tokens import require_buyer
from app.models.buyer import BuyerAccount
from app.routers.suppliers import db_session
from app.services.audit import actor_name, add_audit, audit_public
from app.services.buyers import (
    buyer_public,
    clean_display_name,
    clean_password,
    clean_username,
    clean_use,
    ensure_buyer_accounts,
    ensure_role_coverage,
    find_buyer,
    role_key,
    set_password,
)

router = APIRouter(tags=["buyers"])


class BuyerBody(BaseModel):
    username: str = Field(default="", max_length=80)
    name: str = Field(default="", max_length=100)
    role: str = Field(default="담당", max_length=20)
    use: str = Field(default="사용", max_length=10)
    password: str = Field(default="", max_length=200)


class PasswordBody(BaseModel):
    password: str = Field(default="", max_length=200)


def require_manager(authorization: str | None, db: Session) -> tuple[str, BuyerAccount | None]:
    identity = require_buyer(authorization)
    if identity is None:
        ensure_buyer_accounts(db)
        return actor_name(authorization), None
    account = find_buyer(db, identity["username"])
    return account.display_name, account


def get_account(db: Session, username: str) -> BuyerAccount:
    row = db.scalar(select(BuyerAccount).where(BuyerAccount.username == clean_username(username)))
    if row is None:
        raise AppError("not_found", "계정을 찾을 수 없습니다.", 404)
    return row


@router.get("/buyers")
def list_buyers(
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> list[dict[str, str]]:
    require_buyer(authorization)
    ensure_buyer_accounts(db)
    rows = db.scalars(select(BuyerAccount).order_by(BuyerAccount.username)).all()
    return [buyer_public(row) for row in rows]


@router.post("/buyers", status_code=201)
def create_buyer(
    body: BuyerBody,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict:
    user, _ = require_manager(authorization, db)
    username = clean_username(body.username)
    name = clean_display_name(body.name)
    role = role_key(body.role)
    use = clean_use(body.use or "사용")
    password = clean_password(body.password)
    ensure_role_coverage(db, next_role=role, next_use=use)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = BuyerAccount(
        username=username,
        display_name=name,
        role=role,
        password_hash="pending",
        password_set_at=now,
        use_status=use,
    )
    set_password(row, password)
    db.add(row)
    audit = add_audit(db, user=user, action="등록", target=username, after=name, note=role_key_to_note(role))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("duplicate_username", "이미 있는 아이디입니다.") from exc
    db.refresh(row)
    db.refresh(audit)
    return {"record": buyer_public(row), "audit": audit_public(audit)}


@router.patch("/buyers/{username}")
def update_buyer(
    username: str,
    body: BuyerBody,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict:
    user, me = require_manager(authorization, db)
    row = get_account(db, username)
    name = clean_display_name(body.name)
    role = role_key(body.role)
    use = clean_use(body.use or "사용")
    if me is not None and me.id == row.id and use == "중지":
        raise AppError("invalid_use", "로그인한 본인 계정은 중지할 수 없습니다.")
    ensure_role_coverage(db, row=row, next_role=role, next_use=use)
    before = row.display_name + "/" + row.role + "/" + row.use_status
    row.display_name = name
    row.role = role
    row.use_status = use
    if body.password.strip():
        set_password(row, body.password)
    audit = add_audit(
        db,
        user=user,
        action="수정",
        target=row.username,
        before=before,
        after=name + "/" + role + "/" + use,
    )
    db.commit()
    db.refresh(row)
    db.refresh(audit)
    return {"record": buyer_public(row), "audit": audit_public(audit)}


@router.post("/buyers/{username}/password")
def change_buyer_password(
    username: str,
    body: PasswordBody,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
) -> dict:
    user, _ = require_manager(authorization, db)
    row = get_account(db, username)
    set_password(row, body.password)
    audit = add_audit(db, user=user, action="수정", target=row.username, note="비밀번호 변경")
    db.commit()
    db.refresh(row)
    db.refresh(audit)
    return {"record": buyer_public(row), "audit": audit_public(audit)}


def role_key_to_note(role: str) -> str:
    return "승인자" if role == "approver" else "담당"
