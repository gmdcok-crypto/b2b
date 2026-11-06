import hmac
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import Settings, get_settings
from app.core.errors import AppError


def issue_token(
    settings: Settings,
    username: str,
    name: str,
    *,
    role: str = "buyer",
    password_stamp: int | None = None,
) -> tuple[str, int]:
    minutes = settings.jwt_expire_minutes
    if minutes < 5 or minutes > 1440:
        minutes = 720
    expires_in = minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "name": name,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(seconds=expires_in),
    }
    if password_stamp is not None:
        payload["pwd"] = password_stamp
    token = jwt.encode(payload, settings.jwt_secret.strip(), algorithm="HS256")
    return token, expires_in


def read_token(settings: Settings, authorization: str | None) -> dict[str, str]:
    if not settings.auth_ready():
        raise AppError("auth_not_configured", "인증 설정이 없습니다.", 503)
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("unauthorized", "로그인이 필요합니다.", 401)
    raw = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(raw, settings.jwt_secret.strip(), algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AppError("unauthorized", "로그인이 필요합니다.", 401) from exc
    username = str(payload.get("sub") or "")
    if not username:
        raise AppError("unauthorized", "로그인이 필요합니다.", 401)
    identity = {
        "username": username,
        "name": str(payload.get("name") or username),
        "role": str(payload.get("role") or "buyer"),
    }
    if payload.get("pwd") is not None:
        identity["pwd"] = str(payload.get("pwd"))
    return identity


def require_buyer(authorization: str | None) -> None:
    settings = get_settings()
    if not settings.auth_ready():
        return
    if read_token(settings, authorization).get("role") == "supplier":
        raise AppError("forbidden", "구매사 계정으로 초기화하세요.", 403)


def password_matches(given: str, expected: str) -> bool:
    given_bytes = given.encode("utf-8")
    expected_bytes = expected.encode("utf-8")
    if len(given_bytes) != len(expected_bytes):
        return False
    return hmac.compare_digest(given_bytes, expected_bytes)
