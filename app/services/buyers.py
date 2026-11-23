"""구매 계정 시드와 조회."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.passwords import hash_password, verify_password
from app.models.buyer import BUYER_ROLES, BuyerAccount

MIN_PASSWORD = 8
USERNAME_PATTERN_MSG = "아이디는 영문·숫자·._- 만 2~80자로 입력하세요."


def role_label(role: str) -> str:
    if role == "approver":
        return "승인자"
    return "담당"


def role_key(label: str) -> str:
    value = (label or "").strip()
    if value in ("승인자", "approver"):
        return "approver"
    if value in ("담당", "buyer"):
        return "buyer"
    raise AppError("invalid_role", "역할은 담당 또는 승인자입니다.")


def buyer_public(row: BuyerAccount) -> dict[str, str]:
    return {
        "username": row.username,
        "name": row.display_name,
        "role": role_label(row.role),
        "roleKey": row.role,
        "use": row.use_status,
    }


def ensure_buyer_accounts(db: Session, settings: Settings | None = None) -> None:
    """환경 변수 계정은 없을 때만 만든다. 이후 변경은 계정 관리 화면에서 한다."""
    cfg = settings or get_settings()
    if not cfg.auth_ready():
        return
    created = False
    if _create_if_missing(
        db,
        username=cfg.auth_username.strip(),
        display_name=(cfg.auth_display_name.strip() or cfg.auth_username.strip()),
        role="buyer",
        password=cfg.auth_password,
    ):
        created = True
    if _create_if_missing(
        db,
        username=cfg.auth_approver_username.strip(),
        display_name=(cfg.auth_approver_display_name.strip() or cfg.auth_approver_username.strip()),
        role="approver",
        password=cfg.auth_approver_password,
    ):
        created = True
    if created:
        db.commit()


def _create_if_missing(db: Session, *, username: str, display_name: str, role: str, password: str) -> bool:
    if not username or not password or role not in BUYER_ROLES:
        return False
    exists = db.scalar(select(BuyerAccount.id).where(BuyerAccount.username == username))
    if exists is not None:
        return False
    now = datetime.now(timezone.utc).replace(tzinfo=None)
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
    return True


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


def clean_username(value: str) -> str:
    username = value.strip()
    if len(username) < 2 or len(username) > 80:
        raise AppError("invalid_username", USERNAME_PATTERN_MSG)
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if any(ch not in allowed for ch in username):
        raise AppError("invalid_username", USERNAME_PATTERN_MSG)
    return username


def clean_display_name(value: str) -> str:
    name = value.strip()
    if not name or len(name) > 100:
        raise AppError("invalid_name", "이름을 입력하세요.")
    return name


def clean_password(value: str) -> str:
    password = value.strip()
    if len(password) < MIN_PASSWORD:
        raise AppError("invalid_password", "비밀번호는 8자 이상으로 입력하세요.")
    return password


def clean_use(value: str) -> str:
    if value not in ("사용", "중지"):
        raise AppError("invalid_use", "사용 여부는 사용 또는 중지입니다.")
    return value


def set_password(row: BuyerAccount, password: str) -> None:
    row.password_hash = hash_password(clean_password(password))
    row.password_set_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.updated_at = row.password_set_at


def active_role_count(db: Session, role: str, *, exclude_id: int | None = None) -> int:
    stmt = select(func.count()).select_from(BuyerAccount).where(
        BuyerAccount.role == role,
        BuyerAccount.use_status == "사용",
    )
    if exclude_id is not None:
        stmt = stmt.where(BuyerAccount.id != exclude_id)
    return int(db.scalar(stmt) or 0)


def ensure_role_coverage(
    db: Session,
    *,
    row: BuyerAccount | None = None,
    next_role: str | None = None,
    next_use: str | None = None,
) -> None:
    role = next_role if next_role is not None else (row.role if row else None)
    use = next_use if next_use is not None else (row.use_status if row else "사용")
    exclude = row.id if row is not None else None
    buyer_count = active_role_count(db, "buyer", exclude_id=exclude)
    approver_count = active_role_count(db, "approver", exclude_id=exclude)
    if use == "사용" and role == "buyer":
        buyer_count += 1
    if use == "사용" and role == "approver":
        approver_count += 1
    if buyer_count < 1:
        raise AppError("invalid_role", "사용 중인 담당 계정이 하나 이상 있어야 합니다.")
    if approver_count < 1:
        raise AppError("invalid_role", "사용 중인 승인자 계정이 하나 이상 있어야 합니다.")
