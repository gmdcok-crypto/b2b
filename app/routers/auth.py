from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.tokens import issue_token, password_matches, read_token

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(default="", max_length=80)
    password: str = Field(default="", max_length=200)


@router.get("/auth/status")
def auth_status() -> dict[str, bool]:
    return {"configured": get_settings().auth_ready()}


@router.post("/auth/login")
def login(body: LoginRequest) -> dict[str, str | int]:
    settings = get_settings()
    if not settings.auth_ready():
        raise AppError("auth_not_configured", "인증 설정이 없습니다.", 503)
    username = body.username.strip()
    if username != settings.auth_username.strip() or not password_matches(body.password, settings.auth_password):
        raise AppError("unauthorized", "아이디 또는 비밀번호가 올바르지 않습니다.", 401)
    name = settings.auth_display_name.strip() or username
    token, expires_in = issue_token(settings, username, name)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "username": username,
        "name": name,
    }


@router.get("/auth/me")
def me(authorization: str | None = Header(default=None)) -> dict[str, str]:
    return read_token(get_settings(), authorization)
