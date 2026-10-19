"""Активность машин за день по ряду кадров одной камеры (как в clean-mvp, D-018).

По одному кадру работа и простой не различаются: нужно сравнить соседние кадры одной
камеры. Рамки соседних кадров связываются жадно по классу и IoU, а оставшиеся — по
ближайшему центру; для каждой пары — сдвиг центра рамки в долях её размера. Второго
признака clean-mvp (изменение картинки внутри рамки) здесь нет: отпечатки рамок main не
хранит, поэтому серая зона сдвига остаётся «неясно».

Итог по машине: движение есть — работает; нет движения на серии и машина вне зоны —
простаивает (гипотеза); нет движения в зоне или без зоны — неизвестно; пары нет —
неизвестно. Итог по классу за день: «работает» важнее «простаивает», «простаивает» —
важнее «неизвестно».
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domains.camera.zone import bbox_in_zone
from app.domains.observation.models import Activity

BBox = Sequence[float]  # [x1, y1, x2, y2] в долях кадра

# Ниже этого перекрытия две рамки — разные машины, а не одна сместившаяся
LINK_IOU = 0.3
# …если только рядом нет другой: несвязанная рамка того же класса не дальше стольких
# своих размеров — та же машина, проехавшая между кадрами
LINK_FAR = 3.0
# Сдвинулась такая доля связанных машин — подвинули камеру, пара не в счёт. Проверка
# только при трёх и более машинах: по одной сдвиг камеры от езды не отличить
CAMERA_MOVED_SHARE = 0.8
CAMERA_CHECK_MIN = 3


def iou(a: BBox, b: BBox) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def shift(a: BBox, b: BBox) -> float:
    """Сдвиг центра в долях размера самой рамки: дальняя машина с мелкой рамкой меряется
    так же, как ближняя."""
    ax, ay = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    bx, by = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    size = max((a[2] - a[0] + b[2] - b[0]) / 2, (a[3] - a[1] + b[3] - b[1]) / 2, 1e-6)
    return float(((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 / size)


class Verdict(StrEnum):
    MOVED = "moved"
    STILL = "still"
    UNCLEAR = "unclear"


@dataclass(frozen=True)
class ActivityParams:
    still_shift: float = 0.15
    moved_shift: float = 0.35
    max_gap_min: float = 10.0
    idle_min_pairs: int = 3


@dataclass(frozen=True)
class Box:
    equipment_type_id: uuid.UUID
    bbox: BBox


@dataclass(frozen=True)
class Shot:
    """Кадр камеры со временем и его рамки."""

    at: datetime
    boxes: tuple[Box, ...]


@dataclass(frozen=True)
class Step:
    """Пара соседних кадров одной машины."""

    start: datetime
    end: datetime
    verdict: Verdict


@dataclass
class _Track:
    equipment_type_id: uuid.UUID
    boxes: list[tuple[Shot, Box]] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)


@dataclass(frozen=True)
class MachineActivity:
    equipment_type_id: uuid.UUID
    activity: Activity
    basis: str
    in_zone: bool | None


def _verdict(prev: Box, cur: Box, p: ActivityParams) -> Verdict:
    moved_by = shift(prev.bbox, cur.bbox)
    if moved_by > p.moved_shift:
        return Verdict.MOVED
    if moved_by < p.still_shift:
        return Verdict.STILL
    return Verdict.UNCLEAR


def _link(prev: Sequence[Box], cur: Sequence[Box]) -> list[tuple[int, int]]:
    """Жадно: каждой рамке текущего кадра — лучшая свободная того же класса.

    Сначала по перекрытию (IoU). Оставшиеся рамки класса связываются по ближайшему центру
    в пределах LINK_FAR размеров рамки: машина, проехавшая между кадрами больше половины
    своей длины, уже не перекрывается с собой, но это та же машина в движении."""
    used: set[int] = set()
    linked: set[int] = set()
    pairs = []
    for j, c in enumerate(cur):
        best, best_iou = None, LINK_IOU
        for i, q in enumerate(prev):
            if i in used or q.equipment_type_id != c.equipment_type_id:
                continue
            value = iou(q.bbox, c.bbox)
            if value > best_iou:
                best, best_iou = i, value
        if best is not None:
            used.add(best)
            linked.add(j)
            pairs.append((best, j))
    for j, c in enumerate(cur):
        if j in linked:
            continue
        near = [
            (shift(q.bbox, c.bbox), i)
            for i, q in enumerate(prev)
            if i not in used and q.equipment_type_id == c.equipment_type_id
        ]
        near = [(d, i) for d, i in near if d <= LINK_FAR]
        if near:
            _, i = min(near)
            used.add(i)
            pairs.append((i, j))
    return pairs


def _tracks(shots: Sequence[Shot], p: ActivityParams) -> list[_Track]:
    ordered = sorted(shots, key=lambda s: s.at)
    tracks: list[_Track] = []
    current: dict[int, _Track] = {}  # индекс рамки предыдущего кадра → машина
    for n, shot in enumerate(ordered):
        prev = ordered[n - 1] if n else None
        links: list[tuple[int, int]] = []
        if prev is not None:
            gap = (shot.at - prev.at).total_seconds() / 60
            if 0 < gap <= p.max_gap_min:  # за долгий разрыв машина успеет уехать и вернуться
                links = _link(prev.boxes, shot.boxes)
        verdicts = {j: _verdict(prev.boxes[i], shot.boxes[j], p) for i, j in links} if prev else {}
        camera_moved = (
            len(verdicts) >= CAMERA_CHECK_MIN
            and sum(1 for v in verdicts.values() if v is Verdict.MOVED) / len(verdicts)
            >= CAMERA_MOVED_SHARE
        )
        following: dict[int, _Track] = {}
        linked_from = {j: i for i, j in links}
        for j, box in enumerate(shot.boxes):
            if j in linked_from and linked_from[j] in current:
                track = current[linked_from[j]]
                if not camera_moved and prev is not None:
                    track.steps.append(Step(prev.at, shot.at, verdicts[j]))
            else:
                track = _Track(box.equipment_type_id)
                tracks.append(track)
            track.boxes.append((shot, box))
            following[j] = track
        current = following
    return tracks


def _hhmm(moment: datetime) -> str:
    return moment.strftime("%H:%M")


def _still_run(steps: Sequence[Step]) -> list[Step]:
    best: list[Step] = []
    run: list[Step] = []
    for step in steps:
        run = [*run, step] if step.verdict is Verdict.STILL else []
        if len(run) > len(best):
            best = run
    return best


def _judge(
    track: _Track, zone: Sequence[Sequence[float]] | None, camera: str, p: ActivityParams
) -> MachineActivity:
    in_zone = bbox_in_zone(track.boxes[-1][1].bbox, zone)
    zone_text = (
        f"Зона: у камеры «{camera}» не задана"
        if in_zone is None
        else "Зона: внутри зоны"
        if in_zone
        else "Зона: вне зоны"
    )
    kind = track.equipment_type_id
    moved = next((s for s in track.steps if s.verdict is Verdict.MOVED), None)
    if moved is not None:
        motion = f"Движение: машина сместилась между {_hhmm(moved.start)} и {_hhmm(moved.end)}"
        return MachineActivity(kind, Activity.WORKS, f"{motion}\n{zone_text}", in_zone)
    run = _still_run(track.steps)
    if len(run) >= p.idle_min_pairs:
        motion = (
            f"Движение: нет на {len(run) + 1} кадрах подряд "
            f"({_hhmm(run[0].start)}–{_hhmm(run[-1].end)})"
        )
        if in_zone is False:
            return MachineActivity(kind, Activity.IDLE, f"Гипотеза. {motion}\n{zone_text}", False)
        return MachineActivity(kind, Activity.UNKNOWN, f"{motion}\n{zone_text}", in_zone)
    if not track.steps:
        motion = "Движение: пары кадров для сравнения нет (один кадр)"
    else:
        motion = "Движение: не определено — сдвиг в серой зоне или серия короче нужной"
    return MachineActivity(kind, Activity.UNKNOWN, f"{motion}\n{zone_text}", in_zone)


def camera_activity(
    shots: Sequence[Shot],
    *,
    zone: Sequence[Sequence[float]] | None,
    camera: str,
    params: ActivityParams,
) -> list[MachineActivity]:
    """Активность каждой машины на кадрах одной камеры за день."""
    return [_judge(t, zone, camera, params) for t in _tracks(shots, params)]


_RANK = {Activity.WORKS: 0, Activity.IDLE: 1, Activity.UNKNOWN: 2}

NO_SERIES = "Движение: нет серии кадров одной камеры со временем — по одному снимку не видно"


def class_activity(machines: Sequence[MachineActivity]) -> MachineActivity:
    """Итог класса за день по всем машинам и камерам; основание — от машины, давшей итог."""
    assert machines, "нет машин класса"
    return min(machines, key=lambda m: _RANK[m.activity])
