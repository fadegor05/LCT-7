"""Когда снимать кадр со стрима камеры: интервал, часы стройки, сбои.

Снимаем каждый день в часы стройки (`STREAM__HOURS`, по её поясу), не чаще интервала камеры;
после трёх сбоев подряд интервал удваивается, но не дальше `max_interval_s`.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

# Столько сбоев подряд снимаем по обычному интервалу: разовый обрыв сети — не повод реже
FAILURES_BEFORE_BACKOFF = 3


def interval_after_failures(every_s: int, failures: int, max_interval_s: int) -> int:
    extra = max(0, failures - FAILURES_BEFORE_BACKOFF + 1)
    return min(every_s * 2**extra, max(every_s, max_interval_s))


def _aware(moment: datetime) -> datetime:
    # SQLite отдаёт время без пояса; в базе оно хранится в UTC
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def capture_due(
    *,
    now: datetime,
    last_attempt: datetime | None,
    every_s: int,
    failures: int,
    hours: tuple[int, int],
    tz: ZoneInfo,
    max_interval_s: int,
) -> bool:
    local = now.astimezone(tz)
    if not hours[0] <= local.hour < hours[1]:
        return False
    if last_attempt is None:
        return True
    wait = timedelta(seconds=interval_after_failures(every_s, failures, max_interval_s))
    return now - _aware(last_attempt) >= wait
