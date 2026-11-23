from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine = None
_SessionLocal = None


def _set_korea_timezone(dbapi_connection, _connection_record) -> None:
    """MySQL NOW() 등이 한국 시각이 되도록 세션 타임존을 맞춘다. SQLite는 무시한다."""
    try:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SET time_zone = '+09:00'")
        finally:
            cursor.close()
    except Exception:
        return


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        database_url = get_settings().resolved_database_url()
        if not database_url:
            raise RuntimeError("DATABASE_URL 또는 MYSQL_URL이 설정되지 않았습니다.")
        _engine = create_engine(database_url, pool_pre_ping=True)
        event.listen(_engine, "connect", _set_korea_timezone)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_db() -> Generator[Session, None, None]:
    get_engine()
    assert _SessionLocal is not None
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
