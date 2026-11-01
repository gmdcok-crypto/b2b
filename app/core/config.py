from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db.url import to_sqlalchemy_url


class Settings(BaseSettings):
    """실행 설정. 인증 방식은 설계 단계에서 확정한다."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SCM B2B Portal"
    database_url: str | None = None
    mysql_url: str | None = None
    cors_origins: str = ""

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
