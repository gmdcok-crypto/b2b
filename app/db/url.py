def to_sqlalchemy_url(url: str) -> str:
    """Railway가 주는 mysql://, mariadb:// 를 PyMySQL 드라이버 URL로 바꾼다."""
    stripped = url.strip()
    for prefix in ("mysql://", "mariadb://"):
        if stripped.startswith(prefix):
            return "mysql+pymysql://" + stripped[len(prefix) :]
    return stripped
