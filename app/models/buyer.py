"""구매사 로그인 계정.

담당(buyer)과 승인자(approver)를 나눈다. 비밀번호는 해시로만 저장한다.
최초 계정은 환경 변수로 시드한다.
"""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

BUYER_ROLES = ("buyer", "approver")


class BuyerAccount(Base):
    __tablename__ = "buyer_accounts"
    __table_args__ = (
        CheckConstraint("role IN ('buyer', 'approver')", name="ck_buyer_accounts_role"),
        CheckConstraint("use_status IN ('사용', '중지')", name="ck_buyer_accounts_use_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    password_set_at: Mapped[datetime] = mapped_column(DateTime)
    use_status: Mapped[str] = mapped_column(String(10), default="사용", server_default="사용")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
