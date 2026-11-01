from app.db.url import to_sqlalchemy_url


def test_mysql_scheme_uses_pymysql() -> None:
    assert (
        to_sqlalchemy_url("mysql://user:secret@db.internal:3306/scm")
        == "mysql+pymysql://user:secret@db.internal:3306/scm"
    )


def test_mariadb_scheme_uses_pymysql() -> None:
    assert (
        to_sqlalchemy_url("mariadb://user:secret@db.internal:3306/scm")
        == "mysql+pymysql://user:secret@db.internal:3306/scm"
    )


def test_sqlalchemy_url_is_unchanged() -> None:
    url = "mysql+pymysql://user:secret@db.internal:3306/scm"
    assert to_sqlalchemy_url(url) == url
