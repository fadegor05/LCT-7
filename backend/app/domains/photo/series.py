"""Проверка серии времени штампа по камере (перенесено из clean-mvp, observation/series.py).

Кадры одной камеры со временем из штампа упорядочиваются по имени файла и времени
загрузки — так, как их выгрузил регистратор. Кадр выбивается из серии, если его дата
расходится с двумя соседями, согласными между собой по дате, или если его время нарушает
порядок, когда соседи между собой упорядочены. Одиночный кадр не проверяется.

Неуверенно прочитанный штамп принимается, если ближайшие соседи с обеих сторон —
уверенные кадры серии, время лежит между ними и ни один не дальше `max_gap`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

SERIES_OK = "ok"
SERIES_OUTLIER = "series_outlier"


@dataclass(frozen=True)
class StampedFrame:
    id: str
    camera_id: str
    original_name: str
    uploaded_at: datetime
    at: datetime  # местное время штампа


def _order(f: StampedFrame) -> tuple[str, datetime, str]:
    return (f.original_name, f.uploaded_at, f.id)


def _date_outlier(cur: StampedFrame, a: StampedFrame, b: StampedFrame) -> bool:
    """Дата расходится с двумя соседями, которые согласны между собой. Если соседи сами
    из разных дней (камера шлёт по кадру в день), дата кадра ничему не противоречит."""
    return a.at.date() == b.at.date() != cur.at.date()


def _outlier(prev: StampedFrame | None, cur: StampedFrame, nxt: StampedFrame | None) -> bool:
    if prev and nxt:
        if _date_outlier(cur, prev, nxt):
            return True
        return prev.at <= nxt.at and not prev.at <= cur.at <= nxt.at
    return False


def check_series(frames: Sequence[StampedFrame]) -> dict[str, str | None]:
    """Для каждого кадра: `ok`, `series_outlier` или None — проверить нельзя."""
    result: dict[str, str | None] = {}
    by_camera: dict[str, list[StampedFrame]] = {}
    for f in frames:
        by_camera.setdefault(f.camera_id, []).append(f)
    for series in by_camera.values():
        series.sort(key=_order)
        if len(series) < 3:
            ordered = all(a.at <= b.at for a, b in zip(series, series[1:], strict=False))
            for f in series:
                result[f.id] = SERIES_OK if ordered and len(series) == 2 else None
            continue
        inner = {
            series[i].id: _outlier(series[i - 1], series[i], series[i + 1])
            for i in range(1, len(series) - 1)
        }
        for i, cur in enumerate(series):
            if cur.id in inner:
                bad = inner[cur.id]
            else:
                # Крайний кадр сверяется с ближайшим соседом, который сам в порядке
                step = 1 if i == 0 else -1
                ref = next(
                    (
                        series[j]
                        for j in range(i + step, len(series) if step > 0 else -1, step)
                        if not inner.get(series[j].id, False)
                    ),
                    None,
                )
                bad = ref is not None and (cur.at > ref.at if step > 0 else cur.at < ref.at)
                # …и по дате — с двумя ближайшими соседями, если они согласны между собой
                pair = (
                    series[i + step : i + 3 * step : step] if step > 0 else series[i - 2 : i][::-1]
                )
                if len(pair) == 2 and _date_outlier(cur, pair[0], pair[1]):
                    bad = True
            result[cur.id] = SERIES_OUTLIER if bad else SERIES_OK
    return result


def confirm_uncertain(
    confirmed: Sequence[StampedFrame],
    uncertain: Sequence[StampedFrame],
    max_gap: timedelta,
) -> set[str]:
    """Неуверенно прочитанные штампы, которые подтверждает серия камеры.

    Ошибка чтения вида «13:00 между 14:30 и 15:30» серию нарушает и остаётся ручной.
    """
    accepted: set[str] = set()
    by_camera: dict[str, list[tuple[StampedFrame, bool]]] = {}
    for f in confirmed:
        by_camera.setdefault(f.camera_id, []).append((f, True))
    for f in uncertain:
        by_camera.setdefault(f.camera_id, []).append((f, False))
    for series in by_camera.values():
        series.sort(key=lambda item: _order(item[0]))
        for i, (frame, sure) in enumerate(series):
            if sure:
                continue
            before = next((f for f, s in reversed(series[:i]) if s), None)
            after = next((f for f, s in series[i + 1 :] if s), None)
            if before is None or after is None:
                continue
            if (
                before.at <= frame.at <= after.at
                and frame.at - before.at <= max_gap
                and after.at - frame.at <= max_gap
            ):
                accepted.add(frame.id)
    return accepted
