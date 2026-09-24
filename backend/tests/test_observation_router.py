"""HTTP-контракт для наблюдений."""

import uuid
from datetime import date

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.methodology.models import EquipmentType
from app.domains.observation.models import Observation, ObservedEquipment
from app.domains.user.service import UserService


async def seed_stand_user(container: AsyncContainer) -> None:
    """Создать стендового пользователя."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


class TestObservationRouter:
    """Тесты HTTP маршрутов наблюдений."""

    @pytest.mark.asyncio
    async def test_get_list_observations_nonexistent_site_with_404(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /observations для несуществующего сайта возвращает 404."""
        await seed_stand_user(container)

        fake_site_id = uuid.uuid4()
        response = await client.get(f"/sites/{fake_site_id}/observations")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_observation_nonexistent_site_with_404(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /observations/{date} для несуществующего сайта возвращает 404."""
        await seed_stand_user(container)

        fake_site_id = uuid.uuid4()
        response = await client.get(f"/sites/{fake_site_id}/observations/2024-01-01")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_observation_missing_date_with_404(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /observations/{date} для несуществующей даты возвращает 404."""
        await seed_stand_user(container)

        # Создаём сайт
        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Запрашиваем несуществующее наблюдение
        response = await client.get(f"/sites/{site_id}/observations/2024-01-01")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_observations_empty_with_200(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /observations для сайта без наблюдений возвращает 200 и пустой список."""
        await seed_stand_user(container)

        # Создаём сайт
        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Получаем пустой список
        response = await client.get(f"/sites/{site_id}/observations")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_list_observations_with_equipment_with_200(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /observations возвращает список с заполненной техникой (не UUIDs)."""
        await seed_stand_user(container)

        # Создаём сайт
        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Создаём EquipmentType
        equipment_id = uuid.uuid4()
        observation_date = date(2024, 1, 15)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            # Создаём оборудование
            equipment = EquipmentType(id=equipment_id, code="COMP_1", title="Компрессор")
            session.add(equipment)

            # Создаём наблюдение
            observation = Observation(
                site_id=uuid.UUID(site_id),
                observed_on=observation_date,
                photo_count=1,
                observability="high",
                observability_notes=None,
            )
            session.add(observation)
            await session.flush()

            # Создаём observed equipment с заполненными данными
            observed_eq = ObservedEquipment(
                observation_id=observation.id,
                equipment_type_id=equipment_id,
                count_min=2,
                activity="works",
                confidence="high",
            )
            session.add(observed_eq)
            await session.commit()

        # Получаем список
        response = await client.get(f"/sites/{site_id}/observations")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

        obs = data[0]
        assert obs["site_id"] == site_id
        assert obs["observed_on"] == str(observation_date)
        assert obs["photo_count"] == 1
        assert obs["observability"] == "high"
        assert "equipment" in obs
        assert isinstance(obs["equipment"], list)
        assert len(obs["equipment"]) == 1

        # Проверяем, что equipment содержит code/title, не только IDs
        eq = obs["equipment"][0]
        assert eq["equipment_type_id"] == str(equipment_id)
        assert eq["equipment_code"] == "COMP_1"
        assert eq["equipment_title"] == "Компрессор"
        assert eq["count_min"] == 2
        assert eq["activity"] == "works"
        assert eq["confidence"] == "high"

    @pytest.mark.asyncio
    async def test_get_observation_with_equipment_with_200(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /observations/{date} возвращает наблюдение с заполненной техникой."""
        await seed_stand_user(container)

        # Создаём сайт
        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Создаём EquipmentType
        equipment_id = uuid.uuid4()
        observation_date = date(2024, 1, 15)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            # Создаём оборудование
            equipment = EquipmentType(id=equipment_id, code="EXCAV_1", title="Экскаватор")
            session.add(equipment)

            # Создаём наблюдение
            observation = Observation(
                site_id=uuid.UUID(site_id),
                observed_on=observation_date,
                photo_count=2,
                observability="medium",
                observability_notes="недостаточно кадров для высокой наблюдаемости: 2",
            )
            session.add(observation)
            await session.flush()

            # Создаём observed equipment
            observed_eq = ObservedEquipment(
                observation_id=observation.id,
                equipment_type_id=equipment_id,
                count_min=1,
                activity="idle",
                confidence="medium",
            )
            session.add(observed_eq)
            await session.commit()

        # Получаем детали
        response = await client.get(f"/sites/{site_id}/observations/{observation_date}")

        assert response.status_code == 200
        data = response.json()
        assert data["site_id"] == site_id
        assert data["observed_on"] == str(observation_date)
        assert data["photo_count"] == 2
        assert data["observability"] == "medium"
        assert data["observability_notes"] == "недостаточно кадров для высокой наблюдаемости: 2"

        # Проверяем equipment с code/title
        assert "equipment" in data
        assert len(data["equipment"]) == 1
        eq = data["equipment"][0]
        assert eq["equipment_code"] == "EXCAV_1"
        assert eq["equipment_title"] == "Экскаватор"
        assert eq["count_min"] == 1
