"""Снимки-доказательства отклонения (assessment/evidence.py, как в clean-mvp)."""

import uuid
from datetime import date, datetime

from app.domains.assessment.engine import DeviationResult
from app.domains.assessment.evidence import (
    CameraFacts,
    DetectionFacts,
    PhotoFacts,
    select_evidence,
)
from app.domains.assessment.models import DeviationType, Severity
from app.domains.observation.models import Confidence

DRILL, TRUCK = uuid.uuid4(), uuid.uuid4()
K1, K2 = uuid.uuid4(), uuid.uuid4()
CAMERAS = {
    K1: CameraFacts("К-1 · котлован", [[0.0, 0.5], [1.0, 0.5], [1.0, 1.0], [0.0, 1.0]]),
    K2: CameraFacts("К-2 · свайное поле", None),
}
NAMES = {DRILL: "Буровая установка", TRUCK: "Самосвал"}


def _photo(camera, hour, *machines, bbox=(0.1, 0.1, 0.3, 0.9)) -> PhotoFacts:
    return PhotoFacts(
        id=uuid.uuid4(),
        camera_id=camera,
        day=date(2026, 9, 18),
        at=datetime(2026, 9, 18, hour),
        name=f"{hour}.jpg",
        detections=[DetectionFacts(uuid.uuid4(), m, bbox, 0.9) for m in machines],
    )


def _deviation(type_, machine=None) -> DeviationResult:
    return DeviationResult(
        stage_id=None,
        type=type_,
        is_hypothesis=False,
        severity=Severity.ATTENTION,
        confidence=Confidence.HIGH,
        period_start=date(2026, 9, 18),
        period_end=date(2026, 9, 18),
        expected="",
        observed="",
        limits_text="",
        rule_id=None,
        evidence_dates=(date(2026, 9, 18),),
        equipment_type_id=machine,
    )


def test_mismatch_shows_only_frames_with_the_machine_from_different_cameras() -> None:
    photos = [
        _photo(K2, 10, DRILL),
        _photo(K2, 11, DRILL),
        _photo(K2, 12, TRUCK),
        _photo(K1, 13, DRILL),
    ]

    shots = select_evidence(_deviation(DeviationType.STAGE_MISMATCH, DRILL), photos, CAMERAS, NAMES)

    assert [s.caption for s in shots] == [
        "К-1 · котлован: Буровая установка",
        "К-2 · свайное поле: Буровая установка",
        "К-2 · свайное поле: Буровая установка",
    ]
    assert all(s.detection_id is not None for s in shots)
    assert photos[2].id not in {s.photo_id for s in shots}


def test_machine_outside_the_zone_is_no_evidence() -> None:
    outside = _photo(K1, 10, DRILL, bbox=(0.1, 0.0, 0.3, 0.2))

    shots = select_evidence(
        _deviation(DeviationType.STAGE_MISMATCH, DRILL), [outside], CAMERAS, NAMES
    )

    # Рамки в зоне нет — остаётся самый насыщенный кадр дня
    assert [s.caption for s in shots] == ["К-1 · котлован: 18.09"]
    assert shots[0].detection_id is None


def test_missing_equipment_shows_the_busiest_frame_of_each_day() -> None:
    photos = [_photo(K2, 10, TRUCK), _photo(K2, 11, TRUCK, DRILL)]

    shots = select_evidence(_deviation(DeviationType.MISSING_EQUIPMENT), photos, CAMERAS, NAMES)

    assert [s.photo_id for s in shots] == [photos[1].id]
