"""Регрессия: сессии в тестовом контейнере не должны делить один коннект.

Раньше `TestDatabaseProvider` держал единственный физический SQLite-коннект на
весь контейнер (`:memory:` + StaticPool). Закрытие любой сессии на этом коннекте
шлёт ROLLBACK, который может незаметно снести ещё не закоммиченный, но уже
flush()-нутый write другой, независимой сессии — именно так `EquipmentCatalog.all()`
(лениво открывающий и сразу закрывающий свою сессию при первом cold-load,
см. `app/domains/methodology/catalog.py`) однажды снёс flush() другого домена
в middle of test_ml_parity.py. Этот тест воспроизводит тот же паттерн гонки
напрямую и проверяет, что flush()-нутые данные переживают чужую сессию.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.user.models import User


class TestDatabaseSessionIsolation:
    @pytest.mark.asyncio
    async def test_flush_survives_unrelated_session_open_close(self, container) -> None:
        """flush() в одной сессии не должен пострадать от открытия/закрытия другой."""
        user_id = uuid.uuid4()

        async with container() as writer_container:
            session = await writer_container.get(AsyncSession)
            session.add(User(id=user_id, full_name="Test User"))
            await session.flush()  # staged, ещё не закоммичено

            # Имитируем EquipmentCatalog.all(): независимая сессия открывается
            # и сразу закрывается (issuing its own ROLLBACK) прямо посреди
            # незакоммиченной транзакции writer_container.
            async with container() as cold_load_container:
                cold_session = await cold_load_container.get(AsyncSession)
                await cold_session.execute(select(User))

            await session.commit()

        async with container() as verify_container:
            verify_session = await verify_container.get(AsyncSession)
            found = await verify_session.get(User, user_id)
            assert found is not None, (
                "flush()-нутая запись пропала после того, как независимая сессия "
                "открылась и закрылась на середине транзакции — сессии делят один "
                "физический коннект (регрессия StaticPool-хазарда)"
            )
