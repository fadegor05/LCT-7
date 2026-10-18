"""Правило «техника вне зоны» получает положение рамки из зоны камеры снимка."""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.assessment.engine import EngineConfig
from app.domains.assessment.models import DeviationType
from app.domains.assessment.repository import DeviationRepository
from app.domains.camera.models import Camera
from app.domains.methodology.models import (
    EquipmentRequirement,
    EquipmentSet,
    EquipmentType,
    MethodologyRule,
    Obligation,
)
from app.domains.observation.models import Observation, ObservedEquipment
from app.domains.photo.models import Detection, Photo, ProcessingStatus
from app.domains.schedule.models import Schedule, ScheduleStage
from app.domains.site.models import Site
from tests.test_assessment_coordinator import create_coordinator, seed_user

SQUARE = [[0.1, 0.2], [0.9, 0.2], [0.9, 0.95], [0.1, 0.95]]
OUTSIDE = [0.0, 0.5, 0.05, 0.6]  # нижняя кромка (0.025, 0.6) левее зоны
INSIDE = [0.4, 0.5, 0.6, 0.8]  # нижняя кромка (0.5, 0.8) внутри зоны

ENGINE_CONFIG = EngineConfig(
    tolerance_days=3,
    stale_data_days=7,
    no_progress_window_days=5,
    min_confirming_observations=1,
)


async def _seed_site(
    container,
    *,
    camera_zone: list[list[float]] | None,
    with_camera: bool,
    bboxes: list[list[float]],
) -> uuid.UUID:
    """Сайт с этапом, методикой «кран», наблюдением за сегодня и фото с рамками крана."""
    user = await seed_user(container)
    site_id = uuid.uuid4()
    stage_id = uuid.uuid4()
    equipment_type_id = uuid.uuid4()
    obs_date = date.today() - timedelta(days=2)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add(Site(id=site_id, name="Объект", owner_id=user.id))
        schedule = Schedule(id=uuid.uuid4(), site_id=site_id)
        session.add(schedule)
        await session.flush()
        session.add(
            ScheduleStage(
                id=stage_id,
                schedule_id=schedule.id,
                name="Фундамент",
                position=1,
                planned_start=obs_date - timedelta(days=3),
                planned_end=obs_date + timedelta(days=3),
            )
        )
        session.add(EquipmentType(id=equipment_type_id, code="crane", title="Кран", synonyms=[]))
        await session.flush()

        rule_id = uuid.uuid4()
        session.add(
            MethodologyRule(
                id=rule_id,
                site_id=site_id,
                stage_id=stage_id,
                is_verifiable=True,
                unverifiable_reason=None,
            )
        )
        await session.flush()
        set_id = uuid.uuid4()
        session.add(EquipmentSet(id=set_id, rule_id=rule_id, position=1))
        await session.flush()
        session.add(
            EquipmentRequirement(
                id=uuid.uuid4(),
                set_id=set_id,
                equipment_type_id=equipment_type_id,
                min_count=1,
                obligation=Obligation.NORMATIVE.value,
                gesn_code="01.001",
            )
        )

        observation = Observation(
            id=uuid.uuid4(),
            site_id=site_id,
            observed_on=obs_date,
            photo_count=1,
            observability="high",
        )
        session.add(observation)
        await session.flush()
        session.add(
            ObservedEquipment(
                id=uuid.uuid4(),
                observation_id=observation.id,
                equipment_type_id=equipment_type_id,
                count_min=1,
                activity="works",
                confidence="high",
            )
        )

        camera_id = None
        if with_camera:
            camera = Camera(id=uuid.uuid4(), site_id=site_id, name="К-1", zone=camera_zone)
            session.add(camera)
            await session.flush()
            camera_id = camera.id

        photo_id = uuid.uuid4()
        session.add(
            Photo(
                id=photo_id,
                site_id=site_id,
                storage_key=f"sites/{site_id}/photos/{photo_id}.jpg",
                original_name="a.jpg",
                width=200,
                height=200,
                captured_on=obs_date,
                processing_status=ProcessingStatus.DONE.value,
                camera_id=camera_id,
            )
        )
        await session.flush()
        for bbox in bboxes:
            session.add(
                Detection(
                    id=uuid.uuid4(),
                    photo_id=photo_id,
                    equipment_type_id=equipment_type_id,
                    bbox=bbox,
                    score=0.9,
                    model_version="test",
                )
            )
        await session.commit()
    return site_id


async def _out_of_zone_count(container, site_id: uuid.UUID) -> int:
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        deviations = await DeviationRepository(session).list_by_site(site_id)
        return sum(1 for d in deviations if d.type == DeviationType.OUT_OF_ZONE.value)


async def _recompute(container, site_id: uuid.UUID) -> None:
    coordinator = await create_coordinator(container, ENGINE_CONFIG)
    await coordinator.recompute_site(site_id)


@pytest.mark.asyncio
async def test_machine_outside_zone_raises_out_of_zone(container) -> None:
    site_id = await _seed_site(container, camera_zone=SQUARE, with_camera=True, bboxes=[OUTSIDE])

    await _recompute(container, site_id)

    assert await _out_of_zone_count(container, site_id) == 1


@pytest.mark.asyncio
async def test_machine_inside_zone_raises_nothing(container) -> None:
    site_id = await _seed_site(container, camera_zone=SQUARE, with_camera=True, bboxes=[INSIDE])

    await _recompute(container, site_id)

    assert await _out_of_zone_count(container, site_id) == 0


@pytest.mark.asyncio
async def test_one_box_inside_zone_is_enough(container) -> None:
    """Любая рамка типа внутри зоны — техника в зоне, как в clean-mvp (any)."""
    site_id = await _seed_site(
        container, camera_zone=SQUARE, with_camera=True, bboxes=[OUTSIDE, INSIDE]
    )

    await _recompute(container, site_id)

    assert await _out_of_zone_count(container, site_id) == 0


@pytest.mark.asyncio
async def test_photo_without_camera_keeps_old_behaviour(container) -> None:
    site_id = await _seed_site(container, camera_zone=None, with_camera=False, bboxes=[OUTSIDE])

    await _recompute(container, site_id)

    assert await _out_of_zone_count(container, site_id) == 0


@pytest.mark.asyncio
async def test_camera_without_zone_keeps_old_behaviour(container) -> None:
    site_id = await _seed_site(container, camera_zone=None, with_camera=True, bboxes=[OUTSIDE])

    await _recompute(container, site_id)

    assert await _out_of_zone_count(container, site_id) == 0
