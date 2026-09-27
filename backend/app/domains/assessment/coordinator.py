"""Оркестрация переучёта статусов этапов и отклонений (LCT-11)."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol, cast

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import AsOfMode
from app.domains.assessment.engine import (
    DeviationResult,
    EquipmentRequirementInput,
    ObservationInput,
    ObservedEquipmentInput,
    RuleEngine,
    RuleInput,
    StageInput,
)
from app.domains.assessment.models import Deviation, DeviationEvidence, StageStatus, StatusBasis
from app.domains.assessment.repository import (
    DeviationEvidenceRepository,
    DeviationRepository,
    StageStatusRepository,
    StatusBasisRepository,
)
from app.domains.methodology.repository import MethodologyRepository
from app.domains.observation.repository import (
    ObservationRepository,
    ObservedEquipmentRepository,
)
from app.domains.photo.models import ProcessingStatus
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.schedule.repository import ScheduleRepository


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
        self._session = session
        self._today = today
        self._as_of_config = as_of_config

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
        3. Собрать RuleInput dict (rules_by_stage) из методики с требованиями.
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

            # Шаг 2: Собрать StageInput[]
            stages_orm = await self._schedule_repo.list_stages(schedule.id)
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

            # Построить rules_by_stage (только для правил с stage_id)
            rules_by_stage: dict[uuid.UUID, RuleInput] = {}
            for rule in rules_orm:
                if rule.stage_id is None:
                    # Пропускаем базовые правила без привязки к этапу
                    continue

                # Собрать требования для этого правила
                rule_sets = sets_by_rule_id.get(rule.id, [])
                rule_requirements: list[EquipmentRequirementInput] = []
                for s in rule_sets:
                    reqs = requirements_by_set_id.get(s.id, [])
                    for req in reqs:
                        rule_requirements.append(
                            EquipmentRequirementInput(
                                equipment_type_id=req.equipment_type_id,
                                obligation=req.obligation,
                                min_count=req.min_count,
                            )
                        )

                rules_by_stage[rule.stage_id] = RuleInput(
                    stage_id=rule.stage_id,
                    rule_id=rule.id,
                    is_verifiable=rule.is_verifiable,
                    unverifiable_reason=rule.unverifiable_reason,
                    requirements=rule_requirements,
                )

            # Шаг 4: Собрать ObservationInput[]
            observations_orm = await self._observation_repo.list_by_site(site_id)

            # Построить observation_id_by_date для связи basis_dates с observation_id
            observation_id_by_date: dict[date, uuid.UUID] = {}
            for obs in observations_orm:
                observation_id_by_date[obs.observed_on] = obs.id

            observations: list[ObservationInput] = []
            for obs in observations_orm:
                equipment_orm = await self._observed_equipment_repo.list_by_observation(obs.id)
                equipment: list[ObservedEquipmentInput] = [
                    ObservedEquipmentInput(
                        equipment_type_id=e.equipment_type_id,
                        count_min=e.count_min,
                        activity=e.activity,
                        confidence=e.confidence,
                        in_zone=None,  # MVP ограничение: нет зоны
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
            computation = self._engine.compute_site(
                stages, rules_by_stage, observations, reference_date
            )

            # Шаг 6: Персистировать StageStatus (upsert + delete_missing)
            for result in computation.statuses:
                existing = await self._stage_status_repo.get_by_stage(result.stage_id)
                if existing:
                    # Обновить in-place
                    existing.status = result.status.value
                    existing.delay_days = result.delay_days
                    existing.confidence = result.confidence.value
                    existing.confidence_reason = result.confidence_reason
                else:
                    # Создать новую
                    new_status = StageStatus(
                        id=uuid.uuid4(),
                        stage_id=result.stage_id,
                        status=result.status.value,
                        delay_days=result.delay_days,
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

            # Шаг 8: Персистировать Deviation (full replace)
            await self._deviation_repo.delete_by_site(site_id)

            # Создать Deviation объекты в том же порядке, что и computation.deviations
            deviations: list[Deviation] = []
            for dev_result in cast(list[DeviationResult], computation.deviations):
                dev = Deviation(
                    id=uuid.uuid4(),
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
                )
                await self._deviation_repo.add(dev)
                deviations.append(dev)

            # Шаг 9: Персистировать DeviationEvidence
            # Получить все фото для сайта один раз
            all_photos = await self._photo_repo.list_by_site(site_id)

            # Построить dict фото по captured_on
            photos_by_date: dict[date, list] = {}
            for photo in all_photos:
                if photo.captured_on is not None:
                    if photo.captured_on not in photos_by_date:
                        photos_by_date[photo.captured_on] = []
                    photos_by_date[photo.captured_on].append(photo)

            evidence_rows: list[DeviationEvidence] = []
            for dev, dev_result in zip(deviations, computation.deviations, strict=True):
                # Найти фото, которые подходят по дате и статусу обработки
                for evidence_date in dev_result.evidence_dates:
                    matching_photos = photos_by_date.get(evidence_date, [])
                    for photo in matching_photos:
                        if photo.processing_status == ProcessingStatus.DONE.value:
                            evidence_rows.append(
                                DeviationEvidence(
                                    id=uuid.uuid4(),
                                    deviation_id=dev.id,
                                    photo_id=photo.id,
                                    detection_id=None,
                                )
                            )

            if evidence_rows:
                await self._deviation_evidence_repo.add_many(evidence_rows)

            # Шаг 10: Коммитить
            await self._session.commit()

        except Exception:
            await self._session.rollback()
            raise
