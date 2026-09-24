"""Бизнес-логика сведения наблюдений: пересчёт, получение, список."""

import logging
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.observation.models import Observation, ObservedEquipment
from app.domains.observation.policies import (
    ActivityPolicy,
    AggregationPolicy,
    FrameEquipment,
    ObservabilityPolicy,
)
from app.domains.observation.repository import ObservationRepository, ObservedEquipmentRepository
from app.domains.observation.schemas import ObservationRead, ObservedEquipmentRead
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.site.guard import SiteAccessGuard
from app.plugins.exceptions import AppError

logger = logging.getLogger(__name__)


class ObservationService:
    """Сведение фотографий и детекций за дату в наблюдение."""

    def __init__(
        self,
        repository: ObservationRepository,
        equipment_repo: ObservedEquipmentRepository,
        photos: PhotoRepository,
        detections: DetectionRepository,
        session: AsyncSession,
        guard: SiteAccessGuard,
        catalog: EquipmentCatalog,
        aggregation: AggregationPolicy,
        observability: ObservabilityPolicy,
        activity: ActivityPolicy,
    ) -> None:
        """Инициализировать ObservationService.

        Args:
            repository: ObservationRepository для работы с наблюдениями.
            equipment_repo: ObservedEquipmentRepository для работы с техникой.
            photos: PhotoRepository для получения фотографий.
            detections: DetectionRepository для получения детекций.
            session: AsyncSession для DB операций.
            guard: SiteAccessGuard для проверки доступа.
            catalog: EquipmentCatalog для обогащения типов техники.
            aggregation: AggregationPolicy для агрегации детекций.
            observability: ObservabilityPolicy для оценки наблюдаемости.
            activity: ActivityPolicy для оценки активности техники.
        """
        self._repository = repository
        self._equipment_repo = equipment_repo
        self._photos = photos
        self._detections = detections
        self._session = session
        self._guard = guard
        self._catalog = catalog
        self._aggregation = aggregation
        self._observability = observability
        self._activity = activity

    async def recompute(self, site_id: uuid.UUID, observed_on: date) -> Observation | None:
        """Пересчитать наблюдение за дату.

        Алгоритм:
        1. Получить все фото по дате.
        2. Если фото нет, удалить существующее наблюдение (если есть), вернуть None.
        3. Собрать детекции для кадров со статусом "done".
        4. Оценить наблюдаемость по числу фото.
        5. Агрегировать детекции.
        6. Получить предыдущее наблюдение и его bbox'ы.
        7. Собрать текущие bbox'ы.
        8. Создать или обновить Observation.
        9. Создать ObservedEquipment для каждого типа техники.
        10. Заменить все обслуживаемые ряды техники.
        11. Коммитить и вернуть наблюдение.

        Args:
            site_id: ID стройки.
            observed_on: Дата наблюдения.

        Returns:
            Observation если есть фото, None если фото нет.
        """
        # Шаг 1: Получить все фото по дате
        all_photos = await self._photos.list_by_site(site_id)
        day_photos = [p for p in all_photos if p.captured_on == observed_on]

        # Шаг 2: Если нет фото, удалить существующее наблюдение
        if not day_photos:
            existing = await self._repository.get_by_site_and_date(site_id, observed_on)
            if existing:
                await self._repository.delete(existing)
                await self._session.commit()
            return None

        # Шаг 3: Собрать детекции для кадров со статусом "done"
        # Накапливаем две структуры одновременно:
        # - frames: list[list[FrameEquipment]] для агрегации
        # - current_bboxes: dict[equipment_type_id, list[list[float]]] для активности
        frames: list[list[FrameEquipment]] = []
        current_bboxes: dict[uuid.UUID, list[list[float]]] = {}
        date_sources = [p.date_source for p in day_photos]

        for p in day_photos:
            if p.processing_status == "done":
                dets = await self._detections.list_by_photo(p.id)
                frame_equipment = [FrameEquipment(d.equipment_type_id, d.score) for d in dets]
                frames.append(frame_equipment)

                # Накапливаем bbox'ы по типам техники
                for d in dets:
                    if d.equipment_type_id not in current_bboxes:
                        current_bboxes[d.equipment_type_id] = []
                    current_bboxes[d.equipment_type_id].append(d.bbox)
            else:
                # Фото не готово - не добавляем в frames, но учитываем в фото_count
                frames.append([])

        # Шаг 4: Оценить наблюдаемость
        level, notes = self._observability.assess(len(day_photos))

        # Шаг 5: Агрегировать детекции
        aggregated = self._aggregation.aggregate(frames, date_sources)

        # Шаг 6: Получить предыдущее наблюдение и его bbox'ы
        previous_obs = await self._repository.get_previous(site_id, observed_on)
        previous_bboxes: dict[uuid.UUID, list[list[float]]] = {}

        if previous_obs:
            # Перечитать фото/детекции для предыдущей даты
            previous_day_photos = [
                p for p in all_photos if p.captured_on == previous_obs.observed_on
            ]
            for p in previous_day_photos:
                if p.processing_status == "done":
                    dets = await self._detections.list_by_photo(p.id)
                    for d in dets:
                        if d.equipment_type_id not in previous_bboxes:
                            previous_bboxes[d.equipment_type_id] = []
                        previous_bboxes[d.equipment_type_id].append(d.bbox)

        # Шаг 8: Создать или обновить Observation
        observation = await self._repository.get_by_site_and_date(site_id, observed_on)
        if observation is None:
            observation = Observation(site_id=site_id, observed_on=observed_on)
            self._session.add(observation)

        observation.photo_count = len(day_photos)
        observation.observability = level.value
        observation.observability_notes = notes
        await self._session.flush()  # Присваивает id при вставке

        # Шаг 9: Создать ObservedEquipment для каждого типа техники
        rows: list[ObservedEquipment] = []
        for equipment_type_id, agg in aggregated.items():
            act = self._activity.assess(
                current_bboxes.get(equipment_type_id, []),
                previous_bboxes.get(equipment_type_id),
            )
            row = ObservedEquipment(
                observation_id=observation.id,
                equipment_type_id=equipment_type_id,
                count_min=agg.count_min,
                activity=act.value,
                confidence=agg.confidence.value,
            )
            rows.append(row)

        # Шаг 10: Заменить технику в наблюдении
        await self._equipment_repo.replace_for_observation(observation.id, rows)

        # Шаг 11: Коммитить и вернуть
        await self._session.commit()
        return observation

    async def list_observations(self, site_id: uuid.UUID) -> list[ObservationRead]:
        """Получить список наблюдений по сайту.

        Args:
            site_id: ID стройки.

        Returns:
            Список наблюдений с обогащённой техникой.

        Raises:
            AppError(404) если сайт не найден или не принадлежит пользователю.
        """
        await self._guard.require(site_id)
        observations = await self._repository.list_by_site(site_id)

        result: list[ObservationRead] = []
        for obs in observations:
            equipment = await self._build_equipment_list(obs.id)
            obs_read = ObservationRead(
                id=obs.id,
                site_id=obs.site_id,
                observed_on=obs.observed_on,
                photo_count=obs.photo_count,
                observability=obs.observability,
                observability_notes=obs.observability_notes,
                recomputed_at=obs.recomputed_at,
                equipment=equipment,
            )
            result.append(obs_read)

        return result

    async def get_observation(self, site_id: uuid.UUID, observed_on: date) -> ObservationRead:
        """Получить наблюдение по дате.

        Args:
            site_id: ID стройки.
            observed_on: Дата наблюдения.

        Returns:
            Наблюдение с обогащённой техникой.

        Raises:
            AppError(404) если сайт не найден или наблюдение не найдено.
        """
        await self._guard.require(site_id)
        observation = await self._repository.get_by_site_and_date(site_id, observed_on)

        if observation is None:
            raise AppError("Наблюдение не найдено", status_code=404)

        equipment = await self._build_equipment_list(observation.id)
        return ObservationRead(
            id=observation.id,
            site_id=observation.site_id,
            observed_on=observation.observed_on,
            photo_count=observation.photo_count,
            observability=observation.observability,
            observability_notes=observation.observability_notes,
            recomputed_at=observation.recomputed_at,
            equipment=equipment,
        )

    async def _build_equipment_list(self, observation_id: uuid.UUID) -> list[ObservedEquipmentRead]:
        """Собрать список техники для наблюдения с обогащением каталогом.

        Args:
            observation_id: ID наблюдения.

        Returns:
            Список техники с обогащением code/title из каталога.
        """
        equipment_rows = await self._equipment_repo.list_by_observation(observation_id)
        result: list[ObservedEquipmentRead] = []

        for row in equipment_rows:
            info = await self._catalog.by_id(row.equipment_type_id)
            if info is None:
                logger.warning(
                    "Unknown equipment type in observation: id=%s", row.equipment_type_id
                )
                continue

            equipment_read = ObservedEquipmentRead(
                equipment_type_id=row.equipment_type_id,
                equipment_code=info.code,
                equipment_title=info.title,
                count_min=row.count_min,
                activity=row.activity,
                confidence=row.confidence,
            )
            result.append(equipment_read)

        return result
