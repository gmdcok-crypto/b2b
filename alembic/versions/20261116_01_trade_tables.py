"""품목, 계약 단가, 발주, 변경 이력 테이블.

Revision ID: 20261116_01
Revises: 20261105_01
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261116_01"
down_revision: str | None = "20261105_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MYSQL = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("spec", sa.String(length=120), server_default="", nullable=False),
        sa.Column("unit", sa.String(length=10), nullable=False),
        sa.Column("group_name", sa.String(length=20), nullable=False),
        sa.Column("use_status", sa.String(length=10), server_default="사용", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("use_status IN ('사용', '중지')", name="ck_items_use_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_items_code"),
        **_MYSQL,
    )
    op.create_table(
        "prices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=20), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("request_amount", sa.Integer(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("note", sa.String(length=200), server_default="", nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("status IN ('작성', '적용중', '승인대기', '종료')", name="ck_prices_status"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_prices_doc_no"),
        **_MYSQL,
    )
    op.create_index("ix_prices_supplier_id", "prices", ["supplier_id"])
    op.create_index("ix_prices_item_id", "prices", ["item_id"])
    op.create_table(
        "price_histories",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("price_id", sa.BigInteger(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("before_amount", sa.Integer(), nullable=True),
        sa.Column("after_amount", sa.Integer(), nullable=True),
        sa.Column("actor", sa.String(length=100), server_default="", nullable=False),
        sa.Column("note", sa.String(length=200), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["price_id"], ["prices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        **_MYSQL,
    )
    op.create_index("ix_price_histories_price_id", "price_histories", ["price_id"])
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("doc_no", sa.String(length=20), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), nullable=False),
        sa.Column("buyer", sa.String(length=50), server_default="", nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="KRW", nullable=False),
        sa.Column("vat", sa.String(length=10), server_default="별도", nullable=False),
        sa.Column("note", sa.String(length=200), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("status IN ('작성', '확정', '취소')", name="ck_orders_status"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_no", name="uq_orders_doc_no"),
        **_MYSQL,
    )
    op.create_index("ix_orders_supplier_id", "orders", ["supplier_id"])
    op.create_table(
        "order_lines",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("item_code", sa.String(length=20), server_default="", nullable=False),
        sa.Column("name", sa.String(length=100), server_default="", nullable=False),
        sa.Column("spec", sa.String(length=120), server_default="", nullable=False),
        sa.Column("unit", sa.String(length=10), server_default="", nullable=False),
        sa.Column("qty", sa.Float(), server_default="0", nullable=False),
        sa.Column("unit_price", sa.Integer(), server_default="0", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        **_MYSQL,
    )
    op.create_index("ix_order_lines_order_id", "order_lines", ["order_id"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("logged_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("user_name", sa.String(length=100), server_default="", nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("target", sa.String(length=40), server_default="", nullable=False),
        sa.Column("before_text", sa.String(length=100), server_default="", nullable=False),
        sa.Column("after_text", sa.String(length=100), server_default="", nullable=False),
        sa.Column("note", sa.String(length=200), server_default="", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        **_MYSQL,
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_index("ix_order_lines_order_id", table_name="order_lines")
    op.drop_table("order_lines")
    op.drop_index("ix_orders_supplier_id", table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_price_histories_price_id", table_name="price_histories")
    op.drop_table("price_histories")
    op.drop_index("ix_prices_item_id", table_name="prices")
    op.drop_index("ix_prices_supplier_id", table_name="prices")
    op.drop_table("prices")
    op.drop_table("items")
