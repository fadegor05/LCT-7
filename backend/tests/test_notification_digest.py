"""Сводка по объектам: текст, сбор данных, ручной запуск и расписание."""

import uuid
from datetime import UTC, date, datetime

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import DigestSettings, Settings
from app.domains.assessment.models import (
    Deviation,
    HypothesisDecision,
    SiteSummary,
    StageStatus,
)
from app.domains.notification.digest import (
    DigestScheduler,
    SiteDigest,
    StageLag,
    format_delay,
    next_run_after,
    render_digest,
)
from app.domains.schedule.models import Schedule, ScheduleStage
from tests.test_photo_router import seed_stand_user

TODAY = date(2026, 10, 20)


def _site(**kwargs: object) -> SiteDigest:
    base: dict[str, object] = {
        "name": "ЖК «Северный»",
        "verdict": "behind",
        "delay_min": 14,
        "delay_max": 74,
        "critical": 2,
        "attention": 3,
    }
    return SiteDigest(**{**base, **kwargs})  # type: ignore[arg-type]


def test_format_delay_forms() -> None:
    assert format_delay(4, None) == "от 4 дн."
    assert format_delay(4, 6) == "4–6 дн."
    assert format_delay(5, 5) == "5 дн."
    assert format_delay(None, 6) == "до 6 дн."
    assert format_delay(None, None) is None


def test_render_counts_and_site_status() -> None:
    sites = [
        _site(lagging=[StageLag("Сваи", 14, 74), StageLag("Котлован", 48, None)]),
        _site(name="Школа", verdict="no_deviations", critical=0, attention=1),
    ]

    title, body = render_digest(sites, TODAY)

    assert title == "Сводка по объектам на 20.10.2026"
    assert "Объектов: 2. Критичных отклонений: 2, предупреждений: 4." in body
    assert "1. ЖК «Северный»: отставание 14–74 дн." in body
    assert "Критичных отклонений: 2, предупреждений: 3" in body
    assert "отстающие этапы: Сваи (14–74 дн.), Котлован (от 48 дн.)" in body
    assert "2. Школа: в графике" in body


def test_render_collapses_long_stage_list_and_insufficient_data() -> None:
    lagging = [StageLag(f"Этап {i}", 1, 2) for i in range(5)]

    _, body = render_digest([_site(lagging=lagging), _site(verdict="insufficient_data")], TODAY)

    assert "Этап 2 (1–2 дн.) и ещё 2" in body
    assert "Этап 3" not in body
    assert "данных недостаточно" in body


def test_next_run_is_strictly_after_now() -> None:
    settings = DigestSettings(weekday=0, hour_utc=6)

    # вторник → ближайший понедельник
    assert next_run_after(datetime(2026, 10, 20, 12, tzinfo=UTC), settings) == datetime(
        2026, 10, 26, 6, tzinfo=UTC
    )
    # понедельник до часа запуска → в тот же день
    assert next_run_after(datetime(2026, 10, 19, 5, tzinfo=UTC), settings) == datetime(
        2026, 10, 19, 6, tzinfo=UTC
    )
    # ровно в час запуска → уже через неделю, без двойной отправки
    assert next_run_after(datetime(2026, 10, 19, 6, tzinfo=UTC), settings) == datetime(
        2026, 10, 26, 6, tzinfo=UTC
    )


@pytest.fixture
async def site(client: AsyncClient, container: AsyncContainer) -> str:
    await seed_stand_user(container)
    return (await client.post("/sites", json={"name": "Объект"})).json()["id"]


def _deviation(site_id: str, severity: str, *, hypothesis: bool = False) -> Deviation:
    return Deviation(
        site_id=uuid.UUID(site_id),
        type="extra_equipment" if hypothesis else "stale_data",
        is_hypothesis=hypothesis,
        severity=severity,
        confidence="medium",
        period_start=TODAY,
        period_end=TODAY,
        expected="e",
        observed="o",
        limits_text="l",
        equipment_type_id=uuid.UUID(int=1) if hypothesis else None,
    )


async def _seed_site_state(container: AsyncContainer, site_id: str) -> None:
    sid = uuid.UUID(site_id)
    async with container() as request:
        session = await request.get(AsyncSession)
        schedule = Schedule(site_id=sid)
        session.add(schedule)
        await session.flush()
        piles = ScheduleStage(schedule_id=schedule.id, name="Сваи", position=1)
        done = ScheduleStage(schedule_id=schedule.id, name="Разметка", position=2)
        session.add_all([piles, done])
        await session.flush()
        session.add_all(
            [
                StageStatus(
                    stage_id=piles.id,
                    status="behind",
                    delay_days=14,
                    delay_min=14,
                    delay_max=74,
                    confidence="high",
                ),
                StageStatus(stage_id=done.id, status="on_track", confidence="high"),
                SiteSummary(
                    site_id=sid,
                    verdict="behind",
                    delay_days_min=14,
                    delay_days_max=74,
                    reason="r",
                ),
            ]
        )
        rejected = _deviation(site_id, "attention", hypothesis=True)
        session.add_all(
            [
                _deviation(site_id, "critical"),
                _deviation(site_id, "attention"),
                rejected,
            ]
        )
        await session.flush()
        session.add(
            HypothesisDecision(
                site_id=sid,
                deviation_key=f"extra_equipment:-:{uuid.UUID(int=1)}",
                decision="rejected",
                decided_by_name="Инженер",
                decided_at=datetime.now(UTC),
            )
        )
        await session.commit()


async def test_digest_endpoint_builds_text_from_site_state(
    client: AsyncClient, container: AsyncContainer, site: str
) -> None:
    await _seed_site_state(container, site)

    response = await client.post("/notifications/digest")

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["type"] == "digest"
    assert created["link"] == "/sites"
    # Отклонённая гипотеза в счёт не идёт: 1 критичное и 1 предупреждение
    assert "Критичных отклонений: 1, предупреждений: 1" in created["body"]
    assert "Объект: отставание 14–74 дн." in created["body"]
    assert "Сваи (14–74 дн.)" in created["body"]
    assert "Разметка" not in created["body"]
    feed = (await client.get("/notifications")).json()
    assert feed["unread_count"] == 1


async def test_digest_without_sites_is_conflict(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed_stand_user(container)

    response = await client.post("/notifications/digest")

    assert response.status_code == 409
    assert (await client.get("/notifications")).json()["items"] == []


async def test_scheduler_sends_to_every_owner(
    client: AsyncClient, container: AsyncContainer, site: str
) -> None:
    scheduler = DigestScheduler(container, Settings())

    sent = await scheduler.run_once()

    assert sent == 1
    assert len((await client.get("/notifications")).json()["items"]) == 1
