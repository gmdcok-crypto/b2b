"""DATABASE_URL이 있을 때만 Alembic head까지 올린다."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import get_settings


def upgrade_to_head() -> None:
    url = get_settings().resolved_database_url()
    if not url:
        return
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


def main() -> None:
    upgrade_to_head()


if __name__ == "__main__":
    main()
