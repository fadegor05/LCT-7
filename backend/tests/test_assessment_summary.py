"""Итог по объекту (engine.summarize): худший этап, оговорки и причины «Недостаточно данных»."""

import uuid
from datetime import date

from app.domains.assessment.engine import (
    EngineConfig,
    ObservationInput,
    StageInput,
    StageStatusResult,
    Verdict,
    summarize,
)
from app.domains.assessment.models import StageStatusValue
from app.domains.observation.models import Confidence

CONFIG = EngineConfig(
    tolerance_days=3, stale_data_days=7, no_progress_window_days=5, min_confirming_observations=2
)
TODAY = date(2026, 9, 18)  # пятница


def _stage(name: str, start: date, end: date) -> StageInput:
    return StageInput(uuid.uuid4(), name, 1, start, end)


def _status(
    stage: StageInput,
    status: StageStatusValue,
    delay: int | None = None,
    *,
    open_: bool = False,
    basis: tuple[date, ...] = (),
) -> StageStatusResult:
    return StageStatusResult(
        stage.stage_id,
        status,
        delay,
        Confidence.HIGH,
        None,
        basis,
        delay_open=open_,
        delay_min=delay,
        delay_max=None if open_ else delay,
    )


def _obs(day: date, observability: str = "high") -> ObservationInput:
    return ObservationInput(day, 10, observability, [])


def test_worst_stage_interval_not_glued_across_stages() -> None:
    """Итог — интервал одного худшего этапа, а не «3–68» из границ разных этапов."""
    piles = _stage("Сваи", date(2026, 7, 1), date(2026, 8, 1))
    pit = _stage("Котлован", date(2026, 8, 1), date(2026, 9, 1))
    statuses = [
        _status(piles, StageStatusValue.BEHIND, 3, basis=(date(2026, 7, 4),)),
        _status(pit, StageStatusValue.NOT_STARTED, 48, open_=True),
    ]

    summary = summarize([piles, pit], statuses, [_obs(TODAY)], TODAY, CONFIG)

    assert summary.verdict is Verdict.BEHIND
    assert (summary.delay_days_min, summary.delay_days_max) == (48, None)
    assert summary.stage_id == pit.stage_id
    assert summary.reason.startswith("Измерено по этапу «Котлован»: плановое начало 01.08")


def test_not_started_is_not_counted_when_last_day_poorly_seen() -> None:
    """«Не начат» держится на высокой наблюдаемости: при низкой последнего дня итога нет."""
    pit = _stage("Котлован", date(2026, 8, 1), date(2026, 9, 1))
    statuses = [_status(pit, StageStatusValue.NOT_STARTED, 48, open_=True)]

    summary = summarize([pit], statuses, [_obs(TODAY, "low")], TODAY, CONFIG)

    assert summary.verdict is Verdict.INSUFFICIENT_DATA
    assert summary.reason == "Наблюдаемость последнего рабочего дня низкая."


def test_behind_keeps_note_when_last_day_poorly_seen() -> None:
    piles = _stage("Сваи", date(2026, 7, 1), date(2026, 8, 1))
    statuses = [_status(piles, StageStatusValue.BEHIND, 10, basis=(date(2026, 7, 11),))]

    summary = summarize([piles], statuses, [_obs(TODAY, "low")], TODAY, CONFIG)

    assert summary.verdict is Verdict.BEHIND
    assert summary.reason.endswith("оценка по прошлым снимкам.")


def test_stale_data_gives_no_verdict() -> None:
    piles = _stage("Сваи", date(2026, 7, 1), date(2026, 8, 1))
    statuses = [_status(piles, StageStatusValue.BEHIND, 10)]

    summary = summarize([piles], statuses, [_obs(date(2026, 9, 1))], TODAY, CONFIG)

    assert summary.verdict is Verdict.INSUFFICIENT_DATA
    assert summary.reason == "Данные устарели: последнее наблюдение 01.09.2026."


def test_on_track_is_no_deviations() -> None:
    piles = _stage("Сваи", date(2026, 9, 1), date(2026, 10, 1))
    statuses = [_status(piles, StageStatusValue.ON_TRACK)]

    summary = summarize([piles], statuses, [_obs(TODAY)], TODAY, CONFIG)

    assert summary.verdict is Verdict.NO_DEVIATIONS


def test_only_unobserved_stages_are_insufficient() -> None:
    piles = _stage("Сваи", date(2026, 9, 1), date(2026, 10, 1))
    statuses = [_status(piles, StageStatusValue.NOT_OBSERVED)]

    summary = summarize([piles], statuses, [_obs(TODAY)], TODAY, CONFIG)

    assert summary.verdict is Verdict.INSUFFICIENT_DATA
    assert summary.reason == "По идущим этапам наблюдаемость недостаточна."
