"""단가 변경요청 공문 첨부 테이블.

Revision ID: 20261122_01
Revises: 20261116_01
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261122_01"
down_revision: str | None = "20261116_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MYSQL = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def upgrade() -> None:
    op.create_table(
        "price_attachments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("price_id", sa.BigInteger(), nullable=False),
        sa.Column("history_id", sa.BigInteger(), nullable=True),
        sa.Column("original_name", sa.String(length=200), nullable=False),
        sa.Column("stored_name", sa.String(length=240), nullable=False),
        sa.Column("content_type", sa.String(length=120), server_default="", nullable=False),
        sa.Column("size_bytes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("uploaded_by", sa.String(length=100), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["history_id"], ["price_histories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["price_id"], ["prices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name", name="uq_price_attachments_stored_name"),
        **_MYSQL,
    )
    op.create_index("ix_price_attachments_price_id", "price_attachments", ["price_id"])


def downgrade() -> None:
    op.drop_index("ix_price_attachments_price_id", table_name="price_attachments")
    op.drop_table("price_attachments")
