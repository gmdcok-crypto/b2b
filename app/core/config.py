from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db.url import to_sqlalchemy_url


class Settings(BaseSettings):
    """실행 설정. 인증 방식은 설계 단계에서 확정한다."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SCM B2B Portal"
    database_url: str | None = None
    mysql_url: str | None = None

    def resolved_database_url(self) -> str | None:
        raw = (self.database_url or "").strip() or (self.mysql_url or "").strip()
        if not raw:
            return None
        return to_sqlalchemy_url(raw)


@lru_cache
def get_settings() -> Settings:
    return Settings()
