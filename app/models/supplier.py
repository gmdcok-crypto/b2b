"""협력사 마스터와 로그인.

구매사가 협력사를 등록하면 suppliers 행이 생긴다. 비밀번호는 아직 없다.
구매사가 1회 링크를 보내면 supplier_invites에 토큰 해시가 생긴다.
협력사가 그 링크에서 협력사코드로 확인하고 비밀번호를 정하면 supplier_accounts에 해시가 저장된다.
다음 접속부터는 협력사코드와 비밀번호로 JWT를 받는다. 링크와 토큰에는 비밀번호를 넣지 않는다.
"""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (CheckConstraint("use_status IN ('사용', '중지')", name="ck_suppliers_use_status"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    biz_no: Mapped[str | None] = mapped_column(String(12), unique=True)
    contact: Mapped[str | None] = mapped_column(String(50))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(120))
    use_status: Mapped[str] = mapped_column(String(10), default="사용", server_default="사용")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SupplierAccount(Base):
    """협력사코드 하나당 비밀번호 하나. 최초 설정 전에는 password_hash가 비어 있다."""

    __tablename__ = "supplier_accounts"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    password_set_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SupplierInvite(Base):
    """1회 링크의 토큰. 원문은 저장하지 않고 해시만 둔다."""

    __tablename__ = "supplier_invites"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
