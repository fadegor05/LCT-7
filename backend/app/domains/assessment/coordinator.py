"""Оркестрация переучёта статусов этапов и отклонений (LCT-11)."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Protocol, cast

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import AsOfMode
from app.domains.assessment.engine import (
    DeviationResult,
    EquipmentRequirementInput,
    KitInput,
    ObservationInput,
    ObservedEquipmentInput,
    RuleEngine,
    RuleInput,
    StageInput,
)
from app.domains.assessment.evidence import (
    CameraFacts,
    DetectionFacts,
    PhotoFacts,
    select_evidence,
)
from app.domains.assessment.models import (
    Deviation,
    DeviationEvidence,
    SiteSummary,
    StageStatus,
    StatusBasis,
    deviation_key,
)
from app.domains.assessment.repository import (
    DeviationEvidenceRepository,
    DeviationRepository,
    StageStatusRepository,
    StatusBasisRepository,
)
from app.domains.camera.models import Camera
from app.domains.camera.zone import bbox_in_zone
from app.domains.methodology.catalog import (
    COARSE_TO_SPECIFIC,
    SPECIFIC_EQUIPMENT_CODES,
    STATIONARY_EQUIPMENT_CODES,
    EquipmentCatalog,
)
from app.domains.methodology.materializer import RuleMaterializer
from app.domains.methodology.repository import MethodologyRepository
from app.domains.observation.repository import (
    ObservationRepository,
    ObservedEquipmentRepository,
)
from app.domains.photo.models import Photo, ProcessingStatus
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.schedule.repository import ScheduleRepository
from app.domains.site.models import Site
from app.plugins.exceptions import AppError


def _periods(
    periods: tuple[tuple[uuid.UUID, date, date], ...], names: dict[uuid.UUID, str]
) -> list[dict[str, str]]:
    """Периоды маркеров для методики: машина, название, с, по (ISO-даты)."""
    return [
        {
            "equipment_type_id": str(kind),
            "name": names.get(kind, str(kind)),
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        for kind, start, end in periods
    ]


def _names(ids: frozenset[uuid.UUID], names: dict[uuid.UUID, str]) -> list[str]:
    """Маркеры этапа — названиями техники по алфавиту."""
    return sorted(names.get(i, str(i)) for i in ids)


class Clock(Protocol):
    """Протокол для callable, возвращающего текущую дату.

    Используется для инъекции дефолтного значения в RecomputeCoordinator,
    чтобы Dishka корректно разрешал зависимость.
    """

    def __call__(self) -> date: ...


@dataclass(frozen=True)
class AsOfConfig:
    """Настройка режима опорной даты расчёта (LCT-14). См. AsOfMode."""

    mode: AsOfMode
    fixed_date: date | None


# Модульный singleton для дефолта конструктора (см. today = date.today выше) —
# избегает B008 (вызов в аргументах по умолчанию); AsOfConfig frozen, безопасно делить.
_DEFAULT_AS_OF_CONFIG = AsOfConfig(mode=AsOfMode.TODAY, fixed_date=None)


class RecomputeCoordinator:
    """Оркестратор полного переучёта статусов этапов и отклонений для объекта (site).

    Собирает данные из всех доменов (график, методика, наблюдения, фото, детекции),
    запускает движок расчёта, и персистирует результаты в БД.
    """

    def __init__(
        self,
        engine: RuleEngine,
        stage_status_repo: StageStatusRepository,
        deviation_repo: DeviationRepository,
        deviation_evidence_repo: DeviationEvidenceRepository,
        status_basis_repo: StatusBasisRepository,
        schedule_repo: ScheduleRepository,
        methodology_repo: MethodologyRepository,
        observation_repo: ObservationRepository,
        observed_equipment_repo: ObservedEquipmentRepository,
        photo_repo: PhotoRepository,
        detection_repo: DetectionRepository,
        equipment_catalog: EquipmentCatalog,
        materializer: RuleMaterializer,
        session: AsyncSession,
        today: Clock = date.today,
        as_of_config: AsOfConfig = _DEFAULT_AS_OF_CONFIG,
    ) -> None:
        """Инициализировать RecomputeCoordinator.

        Args:
            engine: RuleEngine с EngineConfig.
            stage_status_repo: StageStatusRepository.
            deviation_repo: DeviationRepository.
            deviation_evidence_repo: DeviationEvidenceRepository.
            status_basis_repo: StatusBasisRepository.
            schedule_repo: ScheduleRepository.
            methodology_repo: MethodologyRepository.
            observation_repo: ObservationRepository.
            observed_equipment_repo: ObservedEquipmentRepository.
            photo_repo: PhotoRepository.
            detection_repo: DetectionRepository.
            equipment_catalog: EquipmentCatalog — резолвинг названий техники для
                отклонений (LCT-15).
            materializer: RuleMaterializer — создаёт правила из базового набора, если
                методику ещё не открывали (иначе все этапы вышли бы «не проверяемыми»).
            session: AsyncSession для персистирования.
            today: Clock — callable для получения текущей даты (default: date.today).
            as_of_config: AsOfConfig — режим опорной даты (default: today, как раньше).
        """
        self._engine = engine
        self._stage_status_repo = stage_status_repo
        self._deviation_repo = deviation_repo
        self._deviation_evidence_repo = deviation_evidence_repo
        self._status_basis_repo = status_basis_repo
        self._schedule_repo = schedule_repo
        self._methodology_repo = methodology_repo
        self._observation_repo = observation_repo
        self._observed_equipment_repo = observed_equipment_repo
        self._photo_repo = photo_repo
        self._detection_repo = detection_repo
        self._equipment_catalog = equipment_catalog
        self._materializer = materializer
        self._session = session
        self._today = today
        self._as_of_config = as_of_config

    async def _zone_flags(self, photos: Sequence[Photo]) -> dict[tuple[date, uuid.UUID], bool]:
        """Положение техники относительно рабочей зоны камеры за дату.

        Ключ — (дата наблюдения, тип техники). Берутся те же фото и рамки, что сводятся в
        наблюдение: обработанные, с датой съёмки и камерой, у которой есть зона. True — хотя
        бы одна рамка типа внутри зоны; False — все рамки типа на зонированных камерах снаружи.
        Ключа нет, если зонированных рамок типа нет: правило «вне зоны» тогда не срабатывает.
        """
        zoned = [
            p
            for p in photos
            if p.camera_id is not None
            and p.captured_on is not None
            and p.processing_status == ProcessingStatus.DONE.value
        ]
        if not zoned:
            return {}
        result = await self._session.execute(
            select(Camera.id, Camera.zone).where(Camera.id.in_({p.camera_id for p in zoned}))
        )
        zone_by_camera = {camera_id: zone for camera_id, zone in result.all() if zone is not None}
        day_zone_by_photo = {
            p.id: (p.captured_on, zone_by_camera[p.camera_id])
            for p in zoned
            if p.camera_id in zone_by_camera and p.captured_on is not None
        }
        if not day_zone_by_photo:
            return {}

        flags: dict[tuple[date, uuid.UUID], bool] = {}
        detections = await self._detection_repo.list_by_photos(list(day_zone_by_photo))
        for det in detections:
            day, zone = day_zone_by_photo[det.photo_id]
            inside = bbox_in_zone(det.bbox, zone)
            if inside is None:
                continue
            key = (day, det.equipment_type_id)
            flags[key] = flags.get(key, False) or inside
        return flags

    def _resolve_as_of(self, observations: Sequence[ObservationInput]) -> date:
        """Определить опорную дату расчёта для площадки (LCT-14).

        last_observation — дата последнего наблюдения НА ЭТОЙ площадке
        (как в ML-отчёте: as_of = states[-1]["date"]). Нужно для демо на
        площадках из разных лет — общая на всё окружение дата не подходит,
        а "последнее наблюдение" у каждой площадки согласовано с её же
        данными. Площадка без наблюдений — fallback на self._today()
        (мерить нечего). fixed без настроенной даты — тоже fallback на
        self._today() (тихо, не ошибка).
        """
        if self._as_of_config.mode == AsOfMode.LAST_OBSERVATION:
            if observations:
                return max(o.observed_on for o in observations)
            return self._today()

        if self._as_of_config.mode == AsOfMode.FIXED:
            if self._as_of_config.fixed_date is not None:
                return self._as_of_config.fixed_date
            return self._today()

        return self._today()

    async def recompute_site(self, site_id: uuid.UUID) -> None:
        """Полный идемпотентный переучёт статусов и отклонений для объекта.

        Алгоритм:
        1. Получить график по site_id. Если нет -> вернуть (no-op).
        2. Собрать StageInput[] из этапов графика.
        3. Создать недостающие правила из базового набора и собрать RuleInput dict
           (rules_by_stage) из методики с требованиями.
        4. Собрать ObservationInput[] из наблюдений + техники.
        5. Запустить engine.compute_site().
        6. Персистировать StageStatus (upsert + delete_missing).
        7. Персистировать StatusBasis для каждого статуса.
        8. Персистировать Deviation (delete_by_site + add).
        9. Персистировать DeviationEvidence для каждого отклонения.
        10. Закоммитить (с rollback на ошибку).

        Args:
            site_id: ID объекта строительства.

        Raises:
            Выбрасывает исключение на ошибку БД/расчёта (caller решает, как обработать).
        """
        try:
            # Шаг 1: Получить график
            schedule = await self._schedule_repo.get_by_site(site_id)
            if schedule is None:
                return  # Ничего не считаем

            # Шаг 2: Собрать StageInput[] (id берём заранее: после rollback ORM-объекты протухают)
            schedule_id = schedule.id
            stages_orm = await self._schedule_repo.list_stages(schedule_id)

            # Правила методики создаются лениво; пересчёт сразу после загрузки графика
            # должен видеть базовый набор, а не «этап не сопоставлен с методикой».
            try:
                if await self._materializer.materialize(site_id, stages_orm):
                    await self._session.commit()
            except (IntegrityError, AppError):
                # IntegrityError — правила параллельно создал другой запрос (list_rules),
                # берём их. AppError — в справочнике нет техники из базового набора: считаем
                # по тем правилам, что есть, пересчёт из-за этого не срываем.
                await self._session.rollback()
                stages_orm = await self._schedule_repo.list_stages(schedule_id)

            stages: list[StageInput] = [
                StageInput(
                    stage_id=s.id,
                    name=s.name,
                    position=s.position,
                    planned_start=s.planned_start,
                    planned_end=s.planned_end,
                )
                for s in stages_orm
            ]

            # Шаг 3: Собрать RuleInput dict
            rules_orm = await self._methodology_repo.list_rules_by_site(site_id)
            rule_ids = [r.id for r in rules_orm]

            # Получить наборы для всех правил
            sets_orm = await self._methodology_repo.list_sets(rule_ids)

            # Получить все требования для всех наборов
            set_ids = [s.id for s in sets_orm]
            requirements_orm = await self._methodology_repo.list_requirements(set_ids)

            # Построить dict требований по set_id
            requirements_by_set_id: dict[uuid.UUID, list] = {}
            for req in requirements_orm:
                if req.set_id not in requirements_by_set_id:
                    requirements_by_set_id[req.set_id] = []
                requirements_by_set_id[req.set_id].append(req)

            # Построить dict наборов по rule_id
            sets_by_rule_id: dict[uuid.UUID, list] = {}
            for s in sets_orm:
                if s.rule_id not in sets_by_rule_id:
                    sets_by_rule_id[s.rule_id] = []
                sets_by_rule_id[s.rule_id].append(s)

            # Загрузить каталог оборудования один раз для определения specificity
            equipment_catalog_items = await self._equipment_catalog.all()
            equipment_by_id = {item.id: item for item in equipment_catalog_items}

            # Построить rules_by_stage (только для правил с stage_id)
            rules_by_stage: dict[uuid.UUID, RuleInput] = {}
            for rule in rules_orm:
                if rule.stage_id is None:
                    # Пропускаем базовые правила без привязки к этапу
                    continue

                # Собрать требования для этого правила (flat list)
                rule_sets = sets_by_rule_id.get(rule.id, [])
                rule_requirements: list[EquipmentRequirementInput] = []

                # Построить kits из наборов (отсортированы по position)
                kits: list[KitInput] = []
                for s in sorted(rule_sets, key=lambda x: x.position):
                    reqs = requirements_by_set_id.get(s.id, [])
                    kit_requirements: list[EquipmentRequirementInput] = []
                    for req in reqs:
                        # Определить, специально ли это оборудование
                        equipment_info = equipment_by_id.get(req.equipment_type_id)
                        is_specific = (
                            equipment_info is not None
                            and equipment_info.code in SPECIFIC_EQUIPMENT_CODES
                        )

                        # Создать требование
                        equipment_req = EquipmentRequirementInput(
                            equipment_type_id=req.equipment_type_id,
                            obligation=req.obligation,
                            min_count=req.min_count,
                            is_specific=is_specific,
                            group=req.group_code,
                        )

                        # Добавить в kit и flat список
                        kit_requirements.append(equipment_req)
                        rule_requirements.append(equipment_req)

                    # Создать KitInput для этого набора
                    if kit_requirements:  # Пропускаем пустые наборы
                        kits.append(KitInput(position=s.position, requirements=kit_requirements))

                rules_by_stage[rule.stage_id] = RuleInput(
                    stage_id=rule.stage_id,
                    rule_id=rule.id,
                    is_verifiable=rule.is_verifiable,
                    unverifiable_reason=rule.unverifiable_reason,
                    requirements=rule_requirements,
                    kits=tuple(kits),
                )

            # Шаг 4: Собрать ObservationInput[]
            observations_orm = await self._observation_repo.list_by_site(site_id)

            # Построить observation_id_by_date для связи basis_dates с observation_id
            observation_id_by_date: dict[date, uuid.UUID] = {}
            for obs in observations_orm:
                observation_id_by_date[obs.observed_on] = obs.id

            # Фото сайта одним запросом: нужны для зон здесь и для доказательств на шаге 9
            all_photos = await self._photo_repo.list_by_site(site_id)
            zone_flags = await self._zone_flags(all_photos)

            observations: list[ObservationInput] = []
            for obs in observations_orm:
                equipment_orm = await self._observed_equipment_repo.list_by_observation(obs.id)
                equipment: list[ObservedEquipmentInput] = [
                    ObservedEquipmentInput(
                        equipment_type_id=e.equipment_type_id,
                        count_min=e.count_min,
                        activity=e.activity,
                        confidence=e.confidence,
                        in_zone=zone_flags.get((obs.observed_on, e.equipment_type_id)),
                    )
                    for e in equipment_orm
                ]
                observations.append(
                    ObservationInput(
                        observed_on=obs.observed_on,
                        photo_count=obs.photo_count,
                        observability=obs.observability,
                        equipment=equipment,
                    )
                )

            # Шаг 5: Запустить engine
            reference_date = self._resolve_as_of(observations)
            # Переиспользовать equipment_catalog_items загруженный при построении kits
            equipment_names = {item.id: item.title for item in equipment_catalog_items}
            id_by_code = {item.code: item.id for item in equipment_catalog_items}
            coarse = {
                id_by_code[code]: frozenset(id_by_code[c] for c in specific if c in id_by_code)
                for code, specific in COARSE_TO_SPECIFIC.items()
                if code in id_by_code
            }
            stationary = frozenset(
                id_by_code[c] for c in STATIONARY_EQUIPMENT_CODES if c in id_by_code
            )
            # Рабочие дни — свои у каждого объекта (clean-mvp); движок без состояния
            site = await self._session.get(Site, site_id)
            engine = self._engine
            if site is not None and tuple(site.workdays) != engine.config.workdays:
                engine = RuleEngine(replace(engine.config, workdays=tuple(site.workdays)))
            computation = engine.compute_site(
                stages,
                rules_by_stage,
                observations,
                reference_date,
                equipment_names,
                coarse,
                stationary,
            )

            # Шаг 6: Персистировать StageStatus (upsert + delete_missing)
            for result in computation.statuses:
                existing = await self._stage_status_repo.get_by_stage(result.stage_id)
                if existing:
                    # Обновить in-place
                    existing.status = result.status.value
                    existing.delay_days = result.delay_days
                    existing.delay_open = result.delay_open
                    existing.delay_min = result.delay_min
                    existing.delay_max = result.delay_max
                    existing.start_fact = result.start_fact
                    existing.marker_names = _names(result.markers, equipment_names)
                    existing.marker_periods = _periods(result.marker_periods, equipment_names)
                    existing.confidence = result.confidence.value
                    existing.confidence_reason = result.confidence_reason
                else:
                    # Создать новую
                    new_status = StageStatus(
                        id=uuid.uuid4(),
                        stage_id=result.stage_id,
                        status=result.status.value,
                        delay_days=result.delay_days,
                        delay_open=result.delay_open,
                        delay_min=result.delay_min,
                        delay_max=result.delay_max,
                        start_fact=result.start_fact,
                        marker_names=_names(result.markers, equipment_names),
                        marker_periods=_periods(result.marker_periods, equipment_names),
                        confidence=result.confidence.value,
                        confidence_reason=result.confidence_reason,
                    )
                    await self._stage_status_repo.add(new_status)

            # delete_missing: удалить статусы для этапов, которые теперь не начинаются
            keep_stage_ids = [r.stage_id for r in computation.statuses]
            if keep_stage_ids:
                # Если есть статусы, которые нужно сохранить, использовать delete_missing
                await self._stage_status_repo.delete_missing(site_id, keep_stage_ids)
            else:
                # Если нет статусов (окна не начались), удалить все существующие статусы
                all_statuses = await self._stage_status_repo.list_by_site(site_id)
                for status in all_statuses:
                    await self._session.execute(
                        delete(StageStatus).where(StageStatus.id == status.id)
                    )
                    await self._session.flush()

            # Шаг 7: Персистировать StatusBasis для каждого статуса
            for result in computation.statuses:
                status_row = await self._stage_status_repo.get_by_stage(result.stage_id)
                if status_row is None:
                    continue

                # Удалить старые basis
                await self._status_basis_repo.delete_by_status(status_row.id)

                # Создать новые basis для каждой даты в basis_dates
                basis_rows: list[StatusBasis] = []
                for basis_date in result.basis_dates:
                    observation_id = observation_id_by_date.get(basis_date)
                    if observation_id is not None:
                        basis_rows.append(
                            StatusBasis(
                                id=uuid.uuid4(),
                                status_id=status_row.id,
                                observation_id=observation_id,
                            )
                        )

                if basis_rows:
                    await self._status_basis_repo.add_many(basis_rows)

            # Шаг 8: Персистировать Deviation (full replace). id то же, что у отклонения с тем
            # же ключом до пересчёта: открытая карточка, ссылка из уведомления или закладка
            # не ломаются, когда пересчёт пересоздаёт строки
            previous = await self._deviation_repo.ids_by_key(site_id)
            await self._deviation_repo.delete_by_site(site_id)
            used: set[uuid.UUID] = set()

            # Создать Deviation объекты в том же порядке, что и computation.deviations
            deviations: list[Deviation] = []
            for dev_result in cast(list[DeviationResult], computation.deviations):
                key = deviation_key(
                    dev_result.type.value, dev_result.stage_id, dev_result.equipment_type_id
                )
                dev_id = previous.get(key)
                if dev_id is None or dev_id in used:
                    dev_id = uuid.uuid4()
                used.add(dev_id)
                dev = Deviation(
                    id=dev_id,
                    site_id=site_id,
                    stage_id=dev_result.stage_id,
                    type=dev_result.type.value,
                    is_hypothesis=dev_result.is_hypothesis,
                    severity=dev_result.severity.value,
                    confidence=dev_result.confidence.value,
                    period_start=dev_result.period_start,
                    period_end=dev_result.period_end,
                    expected=dev_result.expected,
                    observed=dev_result.observed,
                    limits_text=dev_result.limits_text,
                    rule_id=dev_result.rule_id,
                    title=dev_result.title or None,
                    equipment_type_id=dev_result.equipment_type_id,
                    cause_stage_id=dev_result.cause_stage_id,
                )
                await self._deviation_repo.add(dev)
                deviations.append(dev)

            # Шаг 9: Персистировать DeviationEvidence — до трёх снимков с подписями
            # (clean-mvp, assessment/evidence.py), а не все снимки дат отклонения
            done = [
                p
                for p in all_photos
                if p.captured_on is not None and p.processing_status == ProcessingStatus.DONE.value
            ]
            dets_by_photo: dict[uuid.UUID, list[DetectionFacts]] = {}
            for det in await self._detection_repo.list_by_photos([p.id for p in done]):
                dets_by_photo.setdefault(det.photo_id, []).append(
                    DetectionFacts(det.id, det.equipment_type_id, det.bbox, det.score)
                )
            facts = [
                PhotoFacts(
                    id=p.id,
                    camera_id=p.camera_id,
                    day=p.captured_on,
                    at=p.captured_at,
                    name=p.original_name,
                    detections=dets_by_photo.get(p.id, []),
                )
                for p in done
                if p.captured_on is not None
            ]
            camera_rows = await self._session.execute(
                select(Camera.id, Camera.name, Camera.zone).where(Camera.site_id == site_id)
            )
            cameras = {cid: CameraFacts(name, zone) for cid, name, zone in camera_rows.all()}

            evidence_rows: list[DeviationEvidence] = []
            for dev, dev_result in zip(deviations, computation.deviations, strict=True):
                for shot in select_evidence(dev_result, facts, cameras, equipment_names):
                    evidence_rows.append(
                        DeviationEvidence(
                            id=uuid.uuid4(),
                            deviation_id=dev.id,
                            photo_id=shot.photo_id,
                            detection_id=shot.detection_id,
                            caption=shot.caption,
                        )
                    )

            if evidence_rows:
                await self._deviation_evidence_repo.add_many(evidence_rows)

            # Шаг 9b: Итог по объекту — по той же опорной дате, что статусы
            summary = computation.summary
            row = await self._session.get(SiteSummary, site_id)
            if row is None:
                row = SiteSummary(site_id=site_id)
                self._session.add(row)
            row.verdict = summary.verdict.value
            row.delay_days_min = summary.delay_days_min
            row.delay_days_max = summary.delay_days_max
            row.stage_id = summary.stage_id
            row.reason = summary.reason
            row.as_of = summary.as_of

            # Шаг 10: Коммитить
            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise
