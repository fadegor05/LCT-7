"""ObservationRepository и ObservedEquipmentRepository: тесты доступа к данным."""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.methodology.models import EquipmentType
from app.domains.observation.models import Observation, ObservedEquipment
from app.domains.observation.repository import (
    ObservationRepository,
    ObservedEquipmentRepository,
)
from app.domains.site.models import Site
from app.domains.user.models import User


async def seed_data(
    container,
) -> tuple[uuid.UUID, uuid.UUID, list[tuple[uuid.UUID, date]], list[uuid.UUID]]:
    """Подготовить тестовые данные: пользователя, сайт, наблюдения, оборудование.

    Returns:
        (user_id, site_id, [(observation_id, observed_on), ...], [equipment_type_ids])
    """
    user_id = uuid.uuid4()
    site_id = uuid.uuid4()
    equipment_type_ids = [uuid.uuid4() for _ in range(3)]

    async with container() as request_container:
        session = await request_container.get(AsyncSession)

        # Создаём пользователя
        user = User(id=user_id, full_name="Test User")
        session.add(user)

        # Создаём сайт
        site = Site(id=site_id, name="Test Site", owner_id=user_id)
        session.add(site)

        # Создаём типы оборудования
        for idx, eq_id in enumerate(equipment_type_ids):
            equipment_type = EquipmentType(
                id=eq_id, code=f"EQUIP_{idx}", title=f"Equipment Type {idx}", synonyms=[]
            )
            session.add(equipment_type)

        # Создаём наблюдения за разные даты
        observation_ids = []
        for i, obs_date in enumerate([date(2025, 1, 1), date(2025, 1, 3), date(2025, 1, 5)]):
            obs_id = uuid.uuid4()
            observation_ids.append((obs_id, obs_date))
            observation = Observation(
                id=obs_id,
                site_id=site_id,
                observed_on=obs_date,
                photo_count=i + 1,
                observability="high",
                observability_notes=None,
                recomputed_at=datetime.now(UTC),
            )
            session.add(observation)

            # Добавляем технику для каждого наблюдения
            for j, eq_id in enumerate(equipment_type_ids[:2]):
                eq = ObservedEquipment(
                    id=uuid.uuid4(),
                    observation_id=obs_id,
                    equipment_type_id=eq_id,
                    count_min=i + j + 1,
                    activity="works",
                    confidence="high",
                )
                session.add(eq)

        await session.commit()

    return user_id, site_id, observation_ids, equipment_type_ids


class TestObservationRepository:
    """Тесты ObservationRepository."""

    @pytest.mark.asyncio
    async def test_get_by_site_and_date_returns_matching_observation(self, container) -> None:
        """get_by_site_and_date() возвращает наблюдение по сайту и дате."""
        user_id, site_id, observation_ids, _ = await seed_data(container)
        target_obs_id, target_obs_date = observation_ids[1]  # 2025-01-03

        async with container() as request_container:
            repo = await request_container.get(ObservationRepository)
            observation = await repo.get_by_site_and_date(site_id, target_obs_date)

        assert observation is not None
        assert observation.id == target_obs_id
        assert observation.observed_on == target_obs_date
        assert observation.site_id == site_id

    @pytest.mark.asyncio
    async def test_get_by_site_and_date_returns_none_for_nonexistent_date(self, container) -> None:
        """get_by_site_and_date() возвращает None для несуществующей даты."""
        user_id, site_id, observation_ids, _ = await seed_data(container)

        async with container() as request_container:
            repo = await request_container.get(ObservationRepository)
            observation = await repo.get_by_site_and_date(site_id, date(2025, 2, 1))

        assert observation is None

    @pytest.mark.asyncio
    async def test_get_by_site_and_date_returns_none_for_different_site(self, container) -> None:
        """get_by_site_and_date() возвращает None для другого сайта."""
        user_id, site_id, observation_ids, _ = await seed_data(container)
        target_obs_date = observation_ids[0][1]

        other_site_id = uuid.uuid4()

        async with container() as request_container:
            repo = await request_container.get(ObservationRepository)
            observation = await repo.get_by_site_and_date(other_site_id, target_obs_date)

        assert observation is None

    @pytest.mark.asyncio
    async def test_list_by_site_returns_all_observations_ordered_desc(self, container) -> None:
        """list_by_site() возвращает все наблюдения, упорядочены по observed_on (убыв.)."""
        user_id, site_id, observation_ids, _ = await seed_data(container)

        async with container() as request_container:
            repo = await request_container.get(ObservationRepository)
            observations = await repo.list_by_site(site_id)

        assert len(observations) == 3
        # Проверяем упорядочивание по observed_on (убывание)
        dates = [obs.observed_on for obs in observations]
        assert dates == sorted(dates, reverse=True)
        # Проверяем, что это наши наблюдения
        ids_returned = {obs.id for obs in observations}
        ids_expected = {obs_id for obs_id, _ in observation_ids}
        assert ids_returned == ids_expected

    @pytest.mark.asyncio
    async def test_get_previous_returns_closest_earlier_date(self, container) -> None:
        """get_previous() возвращает наблюдение с наибольшей датой < before."""
        user_id, site_id, observation_ids, _ = await seed_data(container)
        # observation_ids = [(obs_id_1, 2025-01-01), (obs_id_2, 2025-01-03), (obs_id_3, 2025-01-05)]

        async with container() as request_container:
            repo = await request_container.get(ObservationRepository)
            # Ищем наблюдение перед 2025-01-04: должно быть 2025-01-03
            previous = await repo.get_previous(site_id, date(2025, 1, 4))

        assert previous is not None
        assert previous.observed_on == date(2025, 1, 3)
        assert previous.id == observation_ids[1][0]

    @pytest.mark.asyncio
    async def test_get_previous_picks_closest_not_just_any_earlier(self, container) -> None:
        """get_previous() выбирает самую близкую более раннюю дату, не любую.

        Это критический тест для доД #2 (Review Focus).
        """
        user_id, site_id, observation_ids, _ = await seed_data(container)
        # observation_ids = [(obs_id_1, 2025-01-01), (obs_id_2, 2025-01-03), (obs_id_3, 2025-01-05)]

        async with container() as request_container:
            repo = await request_container.get(ObservationRepository)
            # Ищем наблюдение перед 2025-01-06: должно быть 2025-01-05, а не 2025-01-03
            previous = await repo.get_previous(site_id, date(2025, 1, 6))

        assert previous is not None
        assert previous.observed_on == date(2025, 1, 5)  # Самое позднее среди более ранних
        assert previous.id == observation_ids[2][0]

    @pytest.mark.asyncio
    async def test_get_previous_returns_none_when_no_earlier_observation(self, container) -> None:
        """get_previous() возвращает None, если нет более ранних наблюдений."""
        user_id, site_id, observation_ids, _ = await seed_data(container)

        async with container() as request_container:
            repo = await request_container.get(ObservationRepository)
            # Ищем наблюдение перед 2024-12-31: таких нет
            previous = await repo.get_previous(site_id, date(2024, 12, 31))

        assert previous is None

    @pytest.mark.asyncio
    async def test_get_previous_returns_none_for_empty_site(self, container) -> None:
        """get_previous() возвращает None для сайта без наблюдений."""
        user_id, site_id, observation_ids, _ = await seed_data(container)

        empty_site_id = uuid.uuid4()

        async with container() as request_container:
            repo = await request_container.get(ObservationRepository)
            previous = await repo.get_previous(empty_site_id, date(2025, 1, 10))

        assert previous is None


class TestObservedEquipmentRepository:
    """Тесты ObservedEquipmentRepository."""

    @pytest.mark.asyncio
    async def test_list_by_observation_returns_all_equipment(self, container) -> None:
        """list_by_observation() возвращает всю технику наблюдения."""
        user_id, site_id, observation_ids, _ = await seed_data(container)
        target_obs_id, _ = observation_ids[0]

        async with container() as request_container:
            repo = await request_container.get(ObservedEquipmentRepository)
            equipment = await repo.list_by_observation(target_obs_id)

        # Мы добавили 2 типа оборудования для каждого наблюдения
        assert len(equipment) == 2
        equipment_ids = {eq.equipment_type_id for eq in equipment}
        assert len(equipment_ids) == 2

    @pytest.mark.asyncio
    async def test_replace_for_observation_replaces_all_rows_idempotently(self, container) -> None:
        """replace_for_observation() удаляет старую технику и добавляет новую идемпотентно."""
        user_id, site_id, observation_ids, equipment_type_ids = await seed_data(container)
        target_obs_id, _ = observation_ids[0]

        # Получаем исходную технику
        async with container() as request_container:
            repo = await request_container.get(ObservedEquipmentRepository)
            old_equipment = await repo.list_by_observation(target_obs_id)

        assert len(old_equipment) == 2
        old_type_ids = {eq.equipment_type_id for eq in old_equipment}

        # Создаём новую технику с совсем другими типами
        new_equipment = [
            ObservedEquipment(
                id=uuid.uuid4(),
                observation_id=target_obs_id,
                equipment_type_id=equipment_type_ids[2],  # Третий тип (не использовался ранее)
                count_min=5,
                activity="idle",
                confidence="medium",
            ),
        ]

        # Заменяем
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = await request_container.get(ObservedEquipmentRepository)
            await repo.replace_for_observation(target_obs_id, new_equipment)
            await session.commit()

        # Проверяем результат
        async with container() as request_container:
            repo = await request_container.get(ObservedEquipmentRepository)
            result_equipment = await repo.list_by_observation(target_obs_id)

        # Должна остаться только новая техника
        assert len(result_equipment) == 1
        assert result_equipment[0].equipment_type_id == equipment_type_ids[2]
        assert result_equipment[0].count_min == 5
        assert result_equipment[0].activity == "idle"
        assert result_equipment[0].confidence == "medium"

        # Проверяем, что старая техника действительно удалена
        result_type_ids = {eq.equipment_type_id for eq in result_equipment}
        assert not result_type_ids.intersection(old_type_ids)

    @pytest.mark.asyncio
    async def test_replace_for_observation_with_empty_rows_deletes_all(self, container) -> None:
        """replace_for_observation() с пустым списком удаляет всю технику."""
        user_id, site_id, observation_ids, _ = await seed_data(container)
        target_obs_id, _ = observation_ids[0]

        async with container() as request_container:
            repo = await request_container.get(ObservedEquipmentRepository)
            old_equipment = await repo.list_by_observation(target_obs_id)

        assert len(old_equipment) == 2

        # Заменяем на пусто
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = await request_container.get(ObservedEquipmentRepository)
            await repo.replace_for_observation(target_obs_id, [])
            await session.commit()

        # Проверяем результат
        async with container() as request_container:
            repo = await request_container.get(ObservedEquipmentRepository)
            result_equipment = await repo.list_by_observation(target_obs_id)

        assert len(result_equipment) == 0
