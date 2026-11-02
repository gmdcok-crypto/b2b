from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db.url import to_sqlalchemy_url


class Settings(BaseSettings):
    """실행 설정. 인증은 JWT 액세스 토큰이다."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SCM B2B Portal"
    database_url: str | None = None
    mysql_url: str | None = None
    cors_origins: str = ""
    jwt_secret: str = ""
    jwt_expire_minutes: int = 720
    auth_username: str = ""
    auth_password: str = ""
    auth_display_name: str = ""

    def auth_ready(self) -> bool:
        return bool(self.jwt_secret.strip() and len(self.jwt_secret.strip()) >= 32 and self.auth_username.strip() and self.auth_password)

    def cors_origin_list(self) -> list[str]:
        defaults = [
            "https://gstec.netlify.app",
            "http://localhost:8888",
            "http://127.0.0.1:8888",
            "http://localhost:5500",
            "http://127.0.0.1:5500",
        ]
        extra = [item.strip().rstrip("/") for item in self.cors_origins.split(",") if item.strip()]
        origins: list[str] = []
        for origin in defaults + extra:
            if origin not in origins:
                origins.append(origin)
        return origins

    def resolved_database_url(self) -> str | None:
        raw = (self.database_url or "").strip() or (self.mysql_url or "").strip()
        if not raw:
            return None
        return to_sqlalchemy_url(raw)


@lru_cache
def get_settings() -> Settings:
    return Settings()
