from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.db.base import Base
from app.models import Supplier, SupplierAccount, SupplierInvite


def test_supplier_tables_cover_invite_then_password() -> None:
    supplier = Base.metadata.tables["suppliers"]
    account = Base.metadata.tables["supplier_accounts"]
    invite = Base.metadata.tables["supplier_invites"]

    assert {"code", "name", "biz_no", "contact", "phone", "email", "use_status"} <= set(supplier.columns.keys())
    assert supplier.columns["code"].unique
    assert supplier.columns["name"].unique
    assert supplier.columns["biz_no"].nullable
    assert account.columns["password_hash"].nullable
    assert account.columns["password_set_at"].nullable
    assert invite.columns["token_hash"].unique
    assert invite.columns["used_at"].nullable
    assert any(column.unique for column in account.columns if column.name == "supplier_id")
    assert Supplier.__tablename__ == "suppliers"
    assert SupplierAccount.__tablename__ == "supplier_accounts"
    assert SupplierInvite.__tablename__ == "supplier_invites"


def test_supplier_migration_creates_mysql_compatible_tables(tmp_path) -> None:
    from pathlib import Path

    url = "sqlite:///" + (tmp_path / "scm.sqlite").as_posix()
    project = Path(__file__).resolve().parents[2]
    cfg = Config(str(project / "alembic.ini"))
    cfg.set_main_option("script_location", str(project / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    names = set(inspect(engine).get_table_names())
    assert {"suppliers", "supplier_accounts", "supplier_invites", "alembic_version"} <= names
    supplier_uniques = {item["name"] for item in inspect(engine).get_unique_constraints("suppliers")}
    assert {"uq_suppliers_code", "uq_suppliers_name", "uq_suppliers_biz_no"} <= supplier_uniques
