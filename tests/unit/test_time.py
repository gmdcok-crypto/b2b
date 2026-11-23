from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.time import KST, as_kst, naive_now_kst, now_kst, today_kst


def test_korea_helpers_use_seoul_zone() -> None:
    assert KST.key == "Asia/Seoul"
    assert now_kst().tzinfo == KST
    assert naive_now_kst().tzinfo is None
    assert today_kst() == now_kst().date()
    utc = datetime(2026, 11, 23, 16, 30, tzinfo=ZoneInfo("UTC"))
    assert as_kst(utc).strftime("%Y-%m-%d %H:%M") == "2026-11-24 01:30"
    assert as_kst(datetime(2026, 11, 24, 1, 30)).tzinfo == KST
