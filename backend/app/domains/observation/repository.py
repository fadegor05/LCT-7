"""Доступ к данным наблюдений: сведённые за дату картины по стройке."""

import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import delete, desc, select

from app.core.repository import BaseRepository
from app.domains.observation.models import Observation, ObservedEquipment


class ObservationRepository(BaseRepository[Observation]):
    """Репозиторий наблюдений (сведения за дату)."""

    model = Observation

    async def get_by_site_and_date(
        self, site_id: uuid.UUID, observed_on: date
    ) -> Observation | None:
        """Получить наблюдение по сайту и дате.

        Args:
            site_id: ID стройки.
            observed_on: Дата наблюдения.

        Returns:
            Observation если существует, иначе None.
        """
        result = await self._session.execute(
            select(self.model).where(
                (self.model.site_id == site_id) & (self.model.observed_on == observed_on)
            )
        )
        return result.scalar_one_or_none()

    async def list_by_site(self, site_id: uuid.UUID) -> Sequence[Observation]:
        """Получить наблюдения по сайту.

        Args:
            site_id: ID стройки.

        Returns:
            Список наблюдений, упорядочен по observed_on (убыв.), потом по id.
        """
        result = await self._session.execute(
            select(self.model)
            .where(self.model.site_id == site_id)
            .order_by(desc(self.model.observed_on), self.model.id)
        )
        return result.scalars().all()

    async def get_previous(self, site_id: uuid.UUID, before: date) -> Observation | None:
        """Получить наблюдение того же сайта с наибольшим observed_on < before.

        Args:
            site_id: ID стройки.
            before: Верхняя граница даты (не включается).

        Returns:
            Observation если существует, иначе None.
        """
        result = await self._session.execute(
            select(self.model)
            .where((self.model.site_id == site_id) & (self.model.observed_on < before))
            .order_by(desc(self.model.observed_on))
            .limit(1)
        )
        return result.scalar_one_or_none()


class ObservedEquipmentRepository(BaseRepository[ObservedEquipment]):
    """Репозиторий наблюдаемой техники."""

    model = ObservedEquipment

    async def list_by_observation(self, observation_id: uuid.UUID) -> Sequence[ObservedEquipment]:
        """Получить технику по наблюдению.

        Args:
            observation_id: ID наблюдения.

        Returns:
            Список обнаруженной техники.
        """
        result = await self._session.execute(
            select(self.model).where(self.model.observation_id == observation_id)
        )
        return result.scalars().all()

    async def replace_for_observation(
        self, observation_id: uuid.UUID, rows: Sequence[ObservedEquipment]
    ) -> None:
        """Заменить технику для наблюдения идемпотентно.

        Удаляет все существующие записи техники для наблюдения,
        затем добавляет новые.

        Args:
            observation_id: ID наблюдения.
            rows: Новые записи техники (может быть пусто).
        """
        await self._session.execute(
            delete(self.model).where(self.model.observation_id == observation_id)
        )
        self._session.add_all(rows)
        await self._session.flush()
