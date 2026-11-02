import hmac
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import Settings
from app.core.errors import AppError


def issue_token(settings: Settings, username: str, name: str) -> tuple[str, int]:
    minutes = settings.jwt_expire_minutes
    if minutes < 5 or minutes > 1440:
        minutes = 720
    expires_in = minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "name": name,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(seconds=expires_in),
    }
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
    return {"username": username, "name": str(payload.get("name") or username)}


def password_matches(given: str, expected: str) -> bool:
    given_bytes = given.encode("utf-8")
    expected_bytes = expected.encode("utf-8")
    if len(given_bytes) != len(expected_bytes):
        return False
    return hmac.compare_digest(given_bytes, expected_bytes)
