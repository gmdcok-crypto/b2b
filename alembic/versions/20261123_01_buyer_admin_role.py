"""구매 계정에 관리자(admin) 역할을 추가한다.

Revision ID: 20261123_01
Revises: 20261122_02
Create Date: 2026-11-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261123_01"
down_revision: str | None = "20261122_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("buyer_accounts") as batch:
        batch.drop_constraint("ck_buyer_accounts_role", type_="check")
        batch.create_check_constraint(
            "ck_buyer_accounts_role",
            "role IN ('admin', 'buyer', 'approver')",
        )
    op.execute("UPDATE buyer_accounts SET role = 'admin' WHERE LOWER(username) = 'gstec'")


def downgrade() -> None:
    op.execute("UPDATE buyer_accounts SET role = 'buyer' WHERE role = 'admin'")
    with op.batch_alter_table("buyer_accounts") as batch:
        batch.drop_constraint("ck_buyer_accounts_role", type_="check")
        batch.create_check_constraint(
            "ck_buyer_accounts_role",
            "role IN ('buyer', 'approver')",
        )
