"""업무 날짜·시간은 한국(Asia/Seoul) 기준으로 통일한다."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    return datetime.now(KST)


def today_kst() -> date:
    return now_kst().date()


def naive_now_kst() -> datetime:
    """DB DateTime(timezone 없음)에 넣을 한국 시각."""
    return now_kst().replace(tzinfo=None)


def as_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)
