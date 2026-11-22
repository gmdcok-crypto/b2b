"""품목, 계약 단가, 발주, 변경 이력.

화면의 샘플 목록을 대체한다. 협력사 이름은 저장하지 않고 suppliers.id로 연결한다.
"""

from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (CheckConstraint("use_status IN ('사용', '중지')", name="ck_items_use_status"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    spec: Mapped[str] = mapped_column(String(120), default="", server_default="")
    unit: Mapped[str] = mapped_column(String(10))
    group_name: Mapped[str] = mapped_column(String(20))
    use_status: Mapped[str] = mapped_column(String(10), default="사용", server_default="사용")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (
        CheckConstraint("status IN ('작성', '적용중', '승인대기', '종료')", name="ck_prices_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(20), unique=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"))
    amount: Mapped[int] = mapped_column(Integer)
    request_amount: Mapped[int | None] = mapped_column(Integer)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str] = mapped_column(String(200), default="", server_default="")
    status: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PriceHistory(Base):
    __tablename__ = "price_histories"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    price_id: Mapped[int] = mapped_column(ForeignKey("prices.id", ondelete="CASCADE"))
    entry_date: Mapped[date] = mapped_column(Date)
    entry_type: Mapped[str] = mapped_column(String(20))
    before_amount: Mapped[int | None] = mapped_column(Integer)
    after_amount: Mapped[int | None] = mapped_column(Integer)
    actor: Mapped[str] = mapped_column(String(100), default="", server_default="")
    note: Mapped[str] = mapped_column(String(200), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PriceAttachment(Base):
    """단가 변경요청 공문 첨부."""

    __tablename__ = "price_attachments"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    price_id: Mapped[int] = mapped_column(ForeignKey("prices.id", ondelete="CASCADE"))
    history_id: Mapped[int | None] = mapped_column(ForeignKey("price_histories.id", ondelete="SET NULL"))
    original_name: Mapped[str] = mapped_column(String(200))
    stored_name: Mapped[str] = mapped_column(String(240), unique=True)
    content_type: Mapped[str] = mapped_column(String(120), default="", server_default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    uploaded_by: Mapped[str] = mapped_column(String(100), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint("status IN ('작성', '확정', '취소')", name="ck_orders_status"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    doc_no: Mapped[str] = mapped_column(String(20), unique=True)
    order_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"))
    buyer: Mapped[str] = mapped_column(String(50), default="", server_default="")
    status: Mapped[str] = mapped_column(String(10))
    currency: Mapped[str] = mapped_column(String(10), default="KRW", server_default="KRW")
    vat: Mapped[str] = mapped_column(String(10), default="별도", server_default="별도")
    note: Mapped[str] = mapped_column(String(200), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OrderLine(Base):
    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    line_no: Mapped[int] = mapped_column(Integer)
    item_code: Mapped[str] = mapped_column(String(20), default="", server_default="")
    name: Mapped[str] = mapped_column(String(100), default="", server_default="")
    spec: Mapped[str] = mapped_column(String(120), default="", server_default="")
    unit: Mapped[str] = mapped_column(String(10), default="", server_default="")
    qty: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    unit_price: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    due_date: Mapped[date | None] = mapped_column(Date)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    user_name: Mapped[str] = mapped_column(String(100), default="", server_default="")
    action: Mapped[str] = mapped_column(String(20))
    target: Mapped[str] = mapped_column(String(40), default="", server_default="")
    before_text: Mapped[str] = mapped_column(String(100), default="", server_default="")
    after_text: Mapped[str] = mapped_column(String(100), default="", server_default="")
    note: Mapped[str] = mapped_column(String(200), default="", server_default="")
