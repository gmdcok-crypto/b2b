"""변경 이력을 같은 트랜잭션에 남긴다."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.tokens import read_token
from app.models.catalog import AuditLog


def actor_name(authorization: str | None) -> str:
    if not authorization:
        return "김구매"
    settings = get_settings()
    if not settings.auth_ready():
        return "김구매"
    identity = read_token(settings, authorization)
    return identity.get("name") or identity.get("username") or "김구매"


def caller(authorization: str | None) -> dict[str, str] | None:
    settings = get_settings()
    if not settings.auth_ready():
        return None
    try:
        return read_token(settings, authorization)
    except AppError:
        raise


def add_audit(
    db: Session,
    *,
    user: str,
    action: str,
    target: str,
    before: str = "",
    after: str = "",
    note: str = "",
) -> AuditLog:
    row = AuditLog(
        logged_at=datetime.now(),
        user_name=(user or "")[:100],
        action=action[:20],
        target=(target or "")[:40],
        before_text=(before or "")[:100],
        after_text=(after or "")[:100],
        note=(note or "")[:200],
    )
    db.add(row)
    return row


def audit_public(row: AuditLog) -> dict[str, str]:
    return {
        "at": row.logged_at.strftime("%Y-%m-%d %H:%M"),
        "user": row.user_name,
        "action": row.action,
        "target": row.target,
        "before": row.before_text or "",
        "after": row.after_text or "",
        "note": row.note or "",
    }


def money_text(value: int | None) -> str:
    if value is None:
        return ""
    return f"{int(value):,}"
