"""구매 담당·승인자 계정과 단가 검토완료 상태.

Revision ID: 20261122_02
Revises: 20261122_01
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261122_02"
down_revision: str | None = "20261122_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MYSQL = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def upgrade() -> None:
    op.create_table(
        "buyer_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("password_set_at", sa.DateTime(), nullable=False),
        sa.Column("use_status", sa.String(length=10), server_default="사용", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("role IN ('buyer', 'approver')", name="ck_buyer_accounts_role"),
        sa.CheckConstraint("use_status IN ('사용', '중지')", name="ck_buyer_accounts_use_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_buyer_accounts_username"),
        **_MYSQL,
    )
    with op.batch_alter_table("prices") as batch:
        batch.drop_constraint("ck_prices_status", type_="check")
        batch.create_check_constraint(
            "ck_prices_status",
            "status IN ('작성', '적용중', '승인대기', '검토완료', '종료')",
        )


def downgrade() -> None:
    with op.batch_alter_table("prices") as batch:
        batch.drop_constraint("ck_prices_status", type_="check")
        batch.create_check_constraint(
            "ck_prices_status",
            "status IN ('작성', '적용중', '승인대기', '종료')",
        )
    op.drop_table("buyer_accounts")
