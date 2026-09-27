"""Тест паритета: статусы этапов backend против ML /report на демо-наборе.

Прогоняет через настоящие сервисы бэкенда те же кадры, детекции и график, по которым
ML построил отчёт `fixtures/ml_demo/report.json`, с той же датой расчёта на площадку
(`as_of` из отчёта), и сравнивает статусы этапов.

Тест работает как храповик. Известные расхождения перечислены в KNOWN_DIVERGENCES
вместе с обеими сторонами. Тест падает, если:
- появилось расхождение, которого нет в списке (регрессия бэкенда);
- у известного расхождения изменился статус с любой стороны;
- известное расхождение исчезло (бэкенд догнал ML) — тогда запись надо удалить.
"""

import csv
import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.assessment.coordinator import RecomputeCoordinator
from app.domains.assessment.engine import RuleEngine
from app.domains.assessment.models import StageStatusValue
from app.domains.assessment.repository import (
    DeviationEvidenceRepository,
    DeviationRepository,
    StageStatusRepository,
    StatusBasisRepository,
)
from app.domains.methodology.models import EquipmentType
from app.domains.methodology.repository import MethodologyRepository
from app.domains.methodology.seed import EQUIPMENT_SEED
from app.domains.observation.repository import (
    ObservationRepository,
    ObservedEquipmentRepository,
)
from app.domains.photo.models import Photo, ProcessingStatus
from app.domains.photo.recalculator import ObservationRecalculator
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.schedule.models import Schedule, ScheduleStage
from app.domains.schedule.repository import ScheduleRepository
from app.domains.site.models import Site
from app.domains.user.models import User
from app.domains.user.service import STAND_USER_DEFAULT_NAME, STAND_USER_ID

# Маппинг ML статусов на backend статусы
ML_STATUS_TO_BACKEND: dict[str, StageStatusValue] = {
    "ahead": StageStatusValue.AHEAD,
    "on_track": StageStatusValue.ON_TRACK,
    "behind": StageStatusValue.BEHIND,
    "not_started": StageStatusValue.NOT_STARTED,
    "not_observed": StageStatusValue.NOT_OBSERVED,
    "not_checkable": StageStatusValue.NOT_CHECKED,
}

# Известные расхождения на демо-наборе: (площадка, код этапа) -> (статус ML, статус бэкенда).
# None у бэкенда — этап не получил статуса вовсе. Причины разобраны не до конца; по коду
# движка видно (аудит 25.09): бэкенд не отличает специфичную технику от общей (у ML это
# class_specificity в ml/configs/rules.json); до начала окна этапа движок этап не
# оценивает, поэтому «опережение» там недостижимо; отставание считается от первой даты,
# когда техника попала в кадр, даже если до этого снимков не было.
# Правило: список только сокращается. Добавить запись — значит признать регрессию.
KNOWN_DIVERGENCES: dict[tuple[str, str], tuple[str, str | None]] = {
    # Исправлено (PR #21, фикс общего SQLite StaticPool-хазарда в conftest.py):
    # было ("on_track", "not_checked") — это не настоящая расходимость с ML, а
    # артефакт повреждённого бейзлайна теста. Из-за общего соединения (StaticPool)
    # холодная загрузка EquipmentCatalog в отдельной сессии откатывала
    # незакоммиченный flush правила для этапа p02/12.3.1 ("Устройство котлована"),
    # и этап терялся без правила -> not_checked. После перехода на пофайловый
    # SQLite с обычным пулом (PR #21) каждая сессия — своё соединение, правило не
    # теряется, и реальный статус бэкенда — behind.
    ("p02", "12.3.1"): ("on_track", "behind"),
    ("p02", "12.3.2"): ("on_track", "behind"),
    ("p03", "12.3.4"): ("ahead", None),
    ("p03", "12.3.6"): ("not_started", "not_observed"),
    ("p04", "12.4.28"): ("not_started", "behind"),
    ("p05", "12.3.9"): ("not_started", "behind"),
    ("p08", "12.3.1"): ("on_track", "ahead"),
    ("p08", "12.4.14"): ("not_observed", "not_checked"),
    ("p09", "12.3.2"): ("not_started", "behind"),
    ("p10", "12.3.1"): ("not_started", "behind"),
    ("p10", "12.3.2"): ("not_observed", None),
    ("p11", "12.3.1"): ("not_observed", None),
    ("p11", "12.3.10"): ("not_checkable", None),
}


def load_ml_fixtures() -> tuple[list[dict], list[dict], dict, dict[str, date | None]]:
    """Загружает фиксированные данные из ml_demo.

    Returns:
        (frames, schedule, report, site_as_of_map) где site_as_of_map это dict site_id → as_of date
        (используется ML в match_schedule.py:452 — PER-SITE reference date)
    """
    fixture_dir = Path(__file__).parent / "fixtures" / "ml_demo"

    with open(fixture_dir / "frames.json", encoding="utf-8") as f:
        frames = json.load(f)

    with open(fixture_dir / "schedule_demo.csv", encoding="utf-8") as f:
        schedule = list(csv.DictReader(f, delimiter=";"))

    with open(fixture_dir / "report.json", encoding="utf-8") as f:
        report = json.load(f)

    # ML использует PER-SITE "as_of" из report (ml/tools/match_schedule.py:452)
    site_as_of_map: dict[str, date | None] = {}
    frames_by_site: dict[str, list[str]] = {}

    # Собираем даты фреймов по сайтам для fallback
    for frame in frames:
        site_id = frame.get("site_id", "")
        frame_date = frame.get("date", "")
        if site_id and frame_date:
            if site_id not in frames_by_site:
                frames_by_site[site_id] = []
            frames_by_site[site_id].append(frame_date)

    # Парсим per-site as_of из report, fallback на max frame date для сайта
    for site in report.get("sites", []):
        site_id = site.get("site_id", "")
        as_of_str = site.get("as_of")

        if as_of_str:
            site_as_of_map[site_id] = datetime.strptime(as_of_str, "%Y-%m-%d").date()
        else:
            # Fallback: max дата в frames для этого сайта
            site_frames = frames_by_site.get(site_id, [])
            if site_frames:
                parsed_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in site_frames]
                site_as_of_map[site_id] = max(parsed_dates)
            else:
                site_as_of_map[site_id] = None

    return frames, schedule, report, site_as_of_map


async def seed_equipment(session: AsyncSession) -> dict[str, uuid.UUID]:
    """Вставляет типы оборудования из EQUIPMENT_SEED."""
    code_to_id = {}
    for item in EQUIPMENT_SEED:
        eq_type = EquipmentType(
            id=uuid.uuid4(),
            code=item["code"],
            title=item["title"],
            synonyms=item.get("synonyms", []),
            is_coarse=item.get("is_coarse", False),
        )
        session.add(eq_type)
        code_to_id[item["code"]] = eq_type.id
    await session.commit()
    return code_to_id


async def create_site_with_stand_user(container, site_id_str: str) -> uuid.UUID:
    """Создаёт сайт с STAND_USER как владельцем."""
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        site_db_id = uuid.uuid4()
        site = Site(
            id=site_db_id,
            name=f"Test Site {site_id_str}",
            owner_id=STAND_USER_ID,
        )
        session.add(site)
        await session.commit()
    return site_db_id


async def create_schedule_for_site(
    container, site_db_id: uuid.UUID, schedule_rows: list[dict], site_id_str: str
) -> None:
    """Создаёт расписание со стадиями."""
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        schedule = Schedule(id=uuid.uuid4(), site_id=site_db_id)
        session.add(schedule)
        await session.flush()

        stages_for_site = [r for r in schedule_rows if r["site_id"] == site_id_str]
        stages_for_site.sort(key=lambda r: r["planned_start"])

        for position, stage_row in enumerate(stages_for_site, start=1):
            start = (
                datetime.strptime(stage_row["planned_start"], "%Y-%m-%d").date()
                if stage_row.get("planned_start")
                else None
            )
            end = (
                datetime.strptime(stage_row["planned_end"], "%Y-%m-%d").date()
                if stage_row.get("planned_end")
                else None
            )

            stage = ScheduleStage(
                id=uuid.uuid4(),
                schedule_id=schedule.id,
                name=stage_row["stage_name"],
                position=position,
                planned_start=start,
                planned_end=end,
            )
            session.add(stage)

        await session.commit()


async def insert_photos_and_detections(
    container,
    site_db_id: uuid.UUID,
    site_id_str: str,
    frames: list[dict],
    code_to_id: dict[str, uuid.UUID],
) -> tuple[int, int]:
    """Вставляет фото и детекции. Returns (total_detections, skipped_unknown)."""
    site_frames = [f for f in frames if f.get("site_id") == site_id_str]
    if not site_frames:
        return 0, 0

    unknown_count = 0
    total_detections = 0

    async with container() as request_container:
        session = await request_container.get(AsyncSession)

        for frame in site_frames:
            date_str = frame.get("date", "")
            if not date_str:
                continue
            try:
                captured_on = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            photo_id = uuid.uuid4()
            photo = Photo(
                id=photo_id,
                site_id=site_db_id,
                storage_key=f"{frame['image']}.bin",
                original_name=frame["image"],
                width=frame.get("width", 0),
                height=frame.get("height", 0),
                captured_on=captured_on,
                date_source="external",
                processing_status=ProcessingStatus.DONE.value,
                uploaded_at=datetime.now(UTC),
            )
            session.add(photo)
            await session.flush()

            # Вставляем детекции, маппируя на оборудование
            detections = frame.get("detections", [])
            for det in detections:
                class_code = det.get("class_ours", "")
                total_detections += 1

                if class_code not in code_to_id:
                    unknown_count += 1
                    continue

                from app.domains.photo.models import Detection

                detection = Detection(
                    id=uuid.uuid4(),
                    photo_id=photo_id,
                    equipment_type_id=code_to_id[class_code],
                    bbox=det.get("bbox", [0, 0, 0, 0]),
                    score=det.get("conf", 0.0),
                    model_version="mocs_m_best@test",
                )
                session.add(detection)

        await session.commit()

    return total_detections, unknown_count


async def run_recalculation(
    container, site_db_id: uuid.UUID, reference_date: date | None = None
) -> None:
    """Пересчитывает observations через ObservationRecalculator, потом запускает coordinator.

    Args:
        container: Dishka container
        site_db_id: Site ID to recompute
        reference_date: Optional reference date for assessment (defaults to date.today())
    """
    async with container() as request_container:
        session = await request_container.get(AsyncSession)

        # Получаем все фото
        photo_repo = PhotoRepository(session)
        photos = await photo_repo.list_by_site(site_db_id)

        if not photos:
            return

        # Собираем даты
        from collections import defaultdict

        photos_by_date = defaultdict(list)
        for photo in photos:
            if photo.captured_on:
                photos_by_date[photo.captured_on].append(photo)

        # Используем реальный ObservationRecalculator из container
        recalculator = await request_container.get(ObservationRecalculator)
        for obs_date in sorted(photos_by_date.keys()):
            await recalculator.recompute(site_db_id, obs_date)

    # Запускаем assessment coordinator из DI container
    async with container() as request_container:
        session = await request_container.get(AsyncSession)

        # Получаем зависимости из контейнера
        stage_status_repo = await request_container.get(StageStatusRepository)
        deviation_repo = await request_container.get(DeviationRepository)
        deviation_evidence_repo = await request_container.get(DeviationEvidenceRepository)
        status_basis_repo = await request_container.get(StatusBasisRepository)
        schedule_repo = await request_container.get(ScheduleRepository)
        methodology_repo = await request_container.get(MethodologyRepository)
        observation_repo = await request_container.get(ObservationRepository)
        observed_equipment_repo = await request_container.get(ObservedEquipmentRepository)
        photo_repo = await request_container.get(PhotoRepository)
        detection_repo = await request_container.get(DetectionRepository)
        engine = await request_container.get(RuleEngine)

        # Создаём coordinator с инъектированным reference_date
        def get_reference_date() -> date:
            """Return reference date (injected or today)."""
            return reference_date if reference_date is not None else date.today()

        coordinator = RecomputeCoordinator(
            engine=engine,
            stage_status_repo=stage_status_repo,
            deviation_repo=deviation_repo,
            deviation_evidence_repo=deviation_evidence_repo,
            status_basis_repo=status_basis_repo,
            schedule_repo=schedule_repo,
            methodology_repo=methodology_repo,
            observation_repo=observation_repo,
            observed_equipment_repo=observed_equipment_repo,
            photo_repo=photo_repo,
            detection_repo=detection_repo,
            session=session,
            today=get_reference_date,
        )

        await coordinator.recompute_site(site_db_id)


class TestMLParity:
    """Тест паритета: backend vs ML статусы этапов."""

    @pytest.mark.asyncio
    async def test_parity_all_sites(self, container) -> None:
        """Сравнивает статусы этапов backend'а со статусами из ML-отчёта.

        Тест детерминирован: использует PER-SITE reference date из ML report
        (ml/tools/match_schedule.py:452 — каждый сайт имеет свой as_of).
        Coordinator получает injected reference_date через run_recalculation().
        """
        frames, schedule, report, site_as_of_map = load_ml_fixtures()

        # Подготавливаем БД
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            stand_user = User(id=STAND_USER_ID, full_name=STAND_USER_DEFAULT_NAME)
            session.add(stand_user)
            code_to_id = await seed_equipment(session)

        # Отслеживаем статистику
        total_pairs = 0
        matched_pairs = 0
        mismatched_pairs = []
        total_detections = 0
        total_unknown = 0

        # Проходим по каждому сайту в ML-отчёте
        for ml_site in report.get("sites", []):
            site_id_str = ml_site.get("site_id")
            if not site_id_str:
                continue

            # Получаем per-site reference date из ML report
            site_reference_date = site_as_of_map.get(site_id_str)

            # Создаём сайт
            site_db_id = await create_site_with_stand_user(container, site_id_str)

            # Создаём расписание
            await create_schedule_for_site(container, site_db_id, schedule, site_id_str)

            # Вставляем фото и детекции
            site_total, site_unknown = await insert_photos_and_detections(
                container, site_db_id, site_id_str, frames, code_to_id
            )
            total_detections += site_total
            total_unknown += site_unknown

            # Создаём default правила для сайта
            async with container() as request_container:
                from app.domains.methodology.service import MethodologyService

                session = await request_container.get(AsyncSession)
                methodology_service = await request_container.get(MethodologyService)
                await methodology_service.list_rules(site_db_id)

            # Запускаем пересчёт с per-site reference date из ML report
            await run_recalculation(container, site_db_id, reference_date=site_reference_date)

            # Читаем backend статусы
            async with container() as request_container:
                session = await request_container.get(AsyncSession)
                schedule_repo = ScheduleRepository(session)
                stage_status_repo = StageStatusRepository(session)

                schedule_record = await schedule_repo.get_by_site(site_db_id)
                if not schedule_record:
                    continue

                stmt = select(ScheduleStage).filter_by(schedule_id=schedule_record.id)
                result = await session.execute(stmt)
                stages = result.scalars().all()

                backend_statuses = {}
                for stage in stages:
                    status = await stage_status_repo.get_by_stage(stage.id)
                    if status:
                        backend_statuses[stage.name] = status.status

            # Сравниваем с ML-отчётом
            for ml_stage in ml_site.get("stages", []):
                stage_code = ml_stage.get("stage_code", "")
                stage_name = ml_stage.get("stage_name", "")
                ml_status = ml_stage.get("status", "")

                total_pairs += 1

                backend_status = backend_statuses.get(stage_name)
                expected_backend_status = ML_STATUS_TO_BACKEND.get(ml_status)

                if backend_status == expected_backend_status:
                    matched_pairs += 1
                else:
                    mismatched_pairs.append(
                        (site_id_str, stage_code, stage_name, ml_status, backend_status)
                    )

        # Отчёт
        print("\n📊 Результаты паритета:")
        print(f"  Всего детекций: {total_detections}")
        print(f"  Неизвестные коды (*_unknown): {total_unknown}")
        print(f"  Всего пар (сайт, этап): {total_pairs}")
        pct = 100 * matched_pairs // total_pairs if total_pairs else 0
        print(f"  Совпадений: {matched_pairs}/{total_pairs} ({pct}%)")
        print(f"  Несовпадений: {len(mismatched_pairs)}")

        observed = {
            (site_id, stage_code): (ml_status, backend_status)
            for site_id, stage_code, _name, ml_status, backend_status in mismatched_pairs
        }
        for (site_id, stage_code), (ml_status, backend_status) in sorted(observed.items()):
            print(f"    • {site_id}/{stage_code}: ML={ml_status}, backend={backend_status}")

        new = {k: v for k, v in observed.items() if k not in KNOWN_DIVERGENCES}
        changed = {
            k: (KNOWN_DIVERGENCES[k], v)
            for k, v in observed.items()
            if k in KNOWN_DIVERGENCES and KNOWN_DIVERGENCES[k] != v
        }
        fixed = sorted(k for k in KNOWN_DIVERGENCES if k not in observed)

        assert not new, f"Новые расхождения с ML (регрессия бэкенда): {new}"
        assert not changed, f"Изменились известные расхождения (было -> стало): {changed}"
        assert not fixed, f"Расхождения исчезли, удалите из KNOWN_DIVERGENCES: {fixed}"

        print(f"\n✅ Тест завершён: {matched_pairs}/{total_pairs} совпадений")
