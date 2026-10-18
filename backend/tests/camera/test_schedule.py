"""Когда снимать кадр со стрима: интервал, часы стройки, сбои."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.domains.camera.schedule import capture_due, interval_after_failures

MSK = ZoneInfo("Europe/Moscow")
# Пятница 18.09.2026, 10:00 по Москве = 07:00 UTC
FRIDAY_10 = datetime(2026, 9, 18, 7, 0, tzinfo=UTC)


def due(now, *, last=None, every=300, failures=0, hours=(8, 20)) -> bool:
    return capture_due(
        now=now,
        last_attempt=last,
        every_s=every,
        failures=failures,
        hours=hours,
        tz=MSK,
        max_interval_s=3600,
    )


def test_first_capture_is_due_at_once_within_working_hours() -> None:
    assert due(FRIDAY_10)


def test_waits_for_the_interval_after_the_last_attempt() -> None:
    assert not due(FRIDAY_10, last=FRIDAY_10 - timedelta(seconds=299))
    assert due(FRIDAY_10, last=FRIDAY_10 - timedelta(seconds=300))


def test_naive_last_attempt_from_the_database_is_read_as_utc() -> None:
    # SQLite отдаёт время без пояса; оно то же UTC
    naive_last = (FRIDAY_10 - timedelta(seconds=300)).replace(tzinfo=None)
    assert due(FRIDAY_10, last=naive_last)


def test_only_within_site_hours_end_excluded() -> None:
    # Часы — по поясу стройки, сервер в UTC: 07:59 и 20:00 по Москве — вне окна
    assert not due(datetime(2026, 9, 18, 4, 59, tzinfo=UTC))
    assert due(datetime(2026, 9, 18, 5, 0, tzinfo=UTC))
    assert due(datetime(2026, 9, 18, 16, 59, tzinfo=UTC))
    assert not due(datetime(2026, 9, 18, 17, 0, tzinfo=UTC))


def test_weekends_are_not_excluded() -> None:
    # Рабочих дней у стройки в модели нет: снимаем каждый день в часы стройки
    saturday = FRIDAY_10 + timedelta(days=1)
    assert due(saturday)


def test_interval_doubles_after_three_failures_up_to_an_hour() -> None:
    assert [interval_after_failures(300, n, 3600) for n in range(7)] == [
        300,
        300,
        300,
        600,
        1200,
        2400,
        3600,
    ]
    # Сбои отодвигают следующую попытку, но не дальше часа
    assert not due(FRIDAY_10, last=FRIDAY_10 - timedelta(seconds=599), failures=3)
    assert due(FRIDAY_10, last=FRIDAY_10 - timedelta(seconds=600), failures=3)


def test_backoff_never_goes_below_the_interval_or_past_the_cap() -> None:
    assert interval_after_failures(300, 50, 3600) == 3600
    assert interval_after_failures(7200, 50, 3600) == 7200
