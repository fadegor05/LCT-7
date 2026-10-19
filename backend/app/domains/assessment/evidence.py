"""Снимки-доказательства отклонения: до трёх кадров с подписями (как в clean-mvp,
assessment/evidence.py). Чистая функция: на входе отклонение движка и факты о снимках.

«Несоответствие» и «Лишняя техника» доказывают кадры с рамкой этой машины в рабочей
зоне, по возможности с разных камер. «Нет маркерной техники», «Неполный комплект» и
«Отставание» — самый насыщенный кадр каждой даты окна. «Данные устарели» — последний
кадр. Прежде к отклонению прикладывались все снимки его дат — 32 кадра, где искомой
машины часто нет.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from app.domains.assessment.engine import DeviationResult
from app.domains.assessment.models import DeviationType
from app.domains.camera.zone import bbox_in_zone

MAX_SHOTS = 3


@dataclass(frozen=True)
class DetectionFacts:
    id: uuid.UUID
    equipment_type_id: uuid.UUID
    bbox: Sequence[float]
    score: float


@dataclass(frozen=True)
class PhotoFacts:
    id: uuid.UUID
    camera_id: uuid.UUID | None
    day: date
    at: datetime | None
    name: str
    detections: Sequence[DetectionFacts]


@dataclass(frozen=True)
class CameraFacts:
    name: str
    zone: Sequence[Sequence[float]] | None


@dataclass(frozen=True)
class EvidenceShot:
    photo_id: uuid.UUID
    detection_id: uuid.UUID | None
    caption: str


def _order(p: PhotoFacts) -> tuple[date, datetime, str]:
    return (p.day, p.at or datetime.min, p.name)


def _camera(cameras: Mapping[uuid.UUID, CameraFacts], p: PhotoFacts) -> str:
    camera = cameras.get(p.camera_id) if p.camera_id else None
    return camera.name if camera else "Снимок"


def _busiest(photos: Sequence[PhotoFacts], day: date) -> PhotoFacts | None:
    """Кадр дня с наибольшим числом рамок."""
    of_day = [p for p in photos if p.day == day]
    return max(of_day, key=lambda p: (len(p.detections), _order(p))) if of_day else None


def _with_machine(
    photos: Sequence[PhotoFacts],
    cameras: Mapping[uuid.UUID, CameraFacts],
    machine: uuid.UUID,
    days: Sequence[date],
    names: Mapping[uuid.UUID, str],
) -> list[EvidenceShot]:
    """Кадры с рамкой машины в зоне камеры за даты отклонения, сначала свежие, по
    возможности с разных камер: машина за зоной ничего не доказывает."""
    candidates: list[tuple[PhotoFacts, DetectionFacts]] = []
    for p in sorted((p for p in photos if p.day in set(days)), key=_order, reverse=True):
        camera = cameras.get(p.camera_id) if p.camera_id else None
        boxes = [
            d
            for d in p.detections
            if d.equipment_type_id == machine
            and bbox_in_zone(d.bbox, camera.zone if camera else None) is not False
        ]
        if boxes:
            candidates.append((p, max(boxes, key=lambda d: d.score)))
    shots: list[EvidenceShot] = []
    used: set[uuid.UUID | None] = set()
    for first_pass in (True, False):
        for p, box in candidates:
            if len(shots) == MAX_SHOTS:
                return shots
            if any(s.photo_id == p.id for s in shots) or (first_pass and p.camera_id in used):
                continue
            used.add(p.camera_id)
            caption = f"{_camera(cameras, p)}: {names.get(machine, 'техника')}"
            shots.append(EvidenceShot(p.id, box.id, caption))
    return shots


def select_evidence(
    deviation: DeviationResult,
    photos: Sequence[PhotoFacts],
    cameras: Mapping[uuid.UUID, CameraFacts],
    names: Mapping[uuid.UUID, str],
) -> list[EvidenceShot]:
    days = sorted(deviation.evidence_dates)
    machine = deviation.equipment_type_id
    if deviation.type == DeviationType.STALE_DATA:
        if not photos:
            return []
        last = max(photos, key=_order)
        return [EvidenceShot(last.id, None, "Последний снимок")]
    if machine is not None:
        shots = _with_machine(photos, cameras, machine, days, names)
        if shots:
            return shots
    limit = 2 if deviation.type == DeviationType.NO_PROGRESS else MAX_SHOTS
    shots = []
    for day in days[-limit:]:
        p = _busiest(photos, day)
        if p is not None:
            shots.append(EvidenceShot(p.id, None, f"{_camera(cameras, p)}: {day:%d.%m}"))
    return shots
