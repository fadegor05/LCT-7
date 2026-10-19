"""Проверка серии времени штампа по камере (тесты перенесены из clean-mvp)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domains.photo.series import SERIES_OK, SERIES_OUTLIER, StampedFrame, check_series

MSK = ZoneInfo("Europe/Moscow")
T0 = datetime(2026, 9, 27, 10, 0, tzinfo=MSK)
UP = datetime(2026, 9, 28, 9, 0, tzinfo=MSK)


def _series(*times: datetime, camera: str = "k1") -> list[StampedFrame]:
    return [
        StampedFrame(f"{camera}-{i}", camera, f"{i:03}.jpg", UP, t) for i, t in enumerate(times)
    ]


def _minutes(*ms: int) -> list[datetime]:
    return [T0 + timedelta(minutes=m) for m in ms]


def test_ordered_series_is_ok() -> None:
    frames = _series(*_minutes(0, 5, 10, 15))
    assert set(check_series(frames).values()) == {SERIES_OK}


def test_misread_date_in_the_middle_is_an_outlier() -> None:
    times = _minutes(0, 5, 10)
    times[1] = times[1].replace(month=7)  # «27-07» вместо «27-09»
    result = check_series(_series(*times))
    assert result == {"k1-0": SERIES_OK, "k1-1": SERIES_OUTLIER, "k1-2": SERIES_OK}


def test_misread_hour_breaks_the_order() -> None:
    result = check_series(_series(*_minutes(0, 5, 600, 15, 20)))
    assert [result[f"k1-{i}"] for i in range(5)] == [
        SERIES_OK,
        SERIES_OK,
        SERIES_OUTLIER,
        SERIES_OK,
        SERIES_OK,
    ]


def test_misread_first_and_last_frames() -> None:
    result = check_series(_series(*_minutes(500, 5, 10, 15, -300)))
    assert result["k1-0"] is SERIES_OUTLIER
    assert result["k1-4"] is SERIES_OUTLIER
    assert result["k1-2"] is SERIES_OK


def test_single_frame_is_not_checked() -> None:
    assert check_series(_series(T0)) == {"k1-0": None}


def test_cameras_are_checked_separately() -> None:
    frames = _series(*_minutes(0, 5), camera="k1") + _series(T0, camera="k2")
    result = check_series(frames)
    assert result["k2-0"] is None and result["k1-1"] is SERIES_OK


def test_two_frames_in_order_are_ok_otherwise_unchecked() -> None:
    assert set(check_series(_series(*_minutes(0, 5))).values()) == {SERIES_OK}
    assert set(check_series(_series(*_minutes(5, 0))).values()) == {None}


def test_one_frame_per_day_is_not_an_outlier() -> None:
    times = [T0 + timedelta(days=d) for d in range(5)]
    assert set(check_series(_series(*times)).values()) == {SERIES_OK}


def test_edge_frame_with_misread_month() -> None:
    times = _minutes(0, 5, 10, 15)
    times[0] = times[0].replace(month=7)  # первый кадр: «07» вместо «09», порядок не нарушен
    result = check_series(_series(*times))
    assert result["k1-0"] is SERIES_OUTLIER and result["k1-1"] is SERIES_OK


# ---------- неуверенные штампы, подтверждённые серией ----------

from app.domains.photo.series import confirm_uncertain  # noqa: E402

GAP = timedelta(hours=12)


def _frame(i: int, minutes: int, camera: str = "k1") -> StampedFrame:
    return StampedFrame(f"{camera}-{i}", camera, f"{i:03}.jpg", UP, T0 + timedelta(minutes=minutes))


def test_uncertain_between_confident_neighbours_is_accepted() -> None:
    sure = [_frame(0, 0), _frame(2, 10)]
    assert confirm_uncertain(sure, [_frame(1, 5)], GAP) == {"k1-1"}


def test_misread_that_breaks_the_series_stays_manual() -> None:
    sure = [_frame(0, 270), _frame(2, 330)]  # 14:30 и 15:30
    assert confirm_uncertain(sure, [_frame(1, 180)], GAP) == set()  # «13:00»


def test_needs_confident_neighbours_on_both_sides() -> None:
    assert confirm_uncertain([_frame(0, 0)], [_frame(1, 5)], GAP) == set()
    assert confirm_uncertain([_frame(2, 10)], [_frame(1, 5)], GAP) == set()


def test_several_uncertain_between_confident_neighbours() -> None:
    sure = [_frame(0, 0), _frame(3, 15)]
    assert confirm_uncertain(sure, [_frame(1, 5), _frame(2, 10)], GAP) == {"k1-1", "k1-2"}
    assert confirm_uncertain([_frame(0, 0)], [_frame(1, 5), _frame(2, 10)], GAP) == set()


def test_too_far_neighbours_do_not_confirm() -> None:
    sure = [_frame(0, 0), _frame(2, 60 * 30)]  # сосед через 30 часов
    assert confirm_uncertain(sure, [_frame(1, 60)], GAP) == set()


def test_other_camera_does_not_confirm() -> None:
    sure = [_frame(0, 0, "k2"), _frame(2, 10, "k2")]
    assert confirm_uncertain(sure, [_frame(1, 5)], GAP) == set()
