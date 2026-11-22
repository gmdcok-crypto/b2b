"""구매 계정 시드와 조회."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.passwords import hash_password, verify_password
from app.models.buyer import BUYER_ROLES, BuyerAccount


def role_label(role: str) -> str:
    if role == "approver":
        return "승인자"
    return "담당"


def ensure_buyer_accounts(db: Session, settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    if not cfg.auth_ready():
        return
    _ensure_one(
        db,
        username=cfg.auth_username.strip(),
        display_name=(cfg.auth_display_name.strip() or cfg.auth_username.strip()),
        role="buyer",
        password=cfg.auth_password,
    )
    _ensure_one(
        db,
        username=cfg.auth_approver_username.strip(),
        display_name=(cfg.auth_approver_display_name.strip() or cfg.auth_approver_username.strip()),
        role="approver",
        password=cfg.auth_approver_password,
    )
    db.commit()


def _ensure_one(db: Session, *, username: str, display_name: str, role: str, password: str) -> None:
    if not username or not password or role not in BUYER_ROLES:
        return
    row = db.scalar(select(BuyerAccount).where(BuyerAccount.username == username))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if row is None:
        db.add(
            BuyerAccount(
                username=username[:80],
                display_name=display_name[:100],
                role=role,
                password_hash=hash_password(password),
                password_set_at=now,
                use_status="사용",
            )
        )
        return
    changed = False
    if row.role != role:
        row.role = role
        changed = True
    if row.display_name != display_name[:100]:
        row.display_name = display_name[:100]
        changed = True
    if row.use_status != "사용":
        row.use_status = "사용"
        changed = True
    if not verify_password(password, row.password_hash):
        row.password_hash = hash_password(password)
        row.password_set_at = now
        changed = True
    if changed:
        row.updated_at = now


def authenticate_buyer(db: Session, username: str, password: str) -> BuyerAccount:
    settings = get_settings()
    ensure_buyer_accounts(db, settings)
    row = db.scalar(select(BuyerAccount).where(BuyerAccount.username == username.strip()))
    if row is None or row.use_status != "사용":
        raise AppError("unauthorized", "아이디 또는 비밀번호가 올바르지 않습니다.", 401)
    if not verify_password(password, row.password_hash):
        raise AppError("unauthorized", "아이디 또는 비밀번호가 올바르지 않습니다.", 401)
    return row


def find_buyer(db: Session, username: str) -> BuyerAccount:
    row = db.scalar(select(BuyerAccount).where(BuyerAccount.username == username.strip()))
    if row is None or row.use_status != "사용":
        raise AppError("unauthorized", "로그인이 필요합니다.", 401)
    return row
