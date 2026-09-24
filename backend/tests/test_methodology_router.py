"""HTTP-контракт методологии проверки оборудования на объекте строительства."""

import uuid
from collections.abc import AsyncIterable

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.settings import Settings, get_settings
from app.domains.methodology.provider import MethodologyProvider
from app.domains.methodology.recalculator import StatusRecalculator
from app.domains.methodology.seed import EQUIPMENT_SEED
from app.domains.schedule.provider import ScheduleProvider
from app.domains.site.provider import SiteProvider
from app.domains.user.provider import UserProvider
from app.domains.user.service import UserService
from app.domains.utility.provider import UtilityProvider
from app.main import create_app
from app.models import Base


async def seed_stand_user(container: AsyncContainer) -> None:
    """Создать станд-пользователя если его нет."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


async def seed_equipment_types(container: AsyncContainer) -> None:
    """Загрузить справочник оборудования в БД и прогреть каталог."""
    from app.domains.methodology.catalog import EquipmentCatalog
    from app.domains.methodology.models import EquipmentType

    async with container() as request_container:
        session = await request_container.get(AsyncSession)

        # Вставить типы оборудования
        for equipment_data in EQUIPMENT_SEED:
            equipment_type = EquipmentType(
                code=equipment_data["code"],
                title=equipment_data["title"],
                synonyms=equipment_data["synonyms"],
            )
            session.add(equipment_type)

        await session.commit()

        # Прогреть каталог (сбросит кеш и загрузит из БД)
        catalog = await container.get(EquipmentCatalog)
        await catalog.all()


async def create_site_with_schedule(
    client: AsyncClient, container: AsyncContainer
) -> tuple[uuid.UUID, uuid.UUID]:
    """Создать сайт и импортировать график с несколькими этапами.

    Returns:
        (site_id, schedule_id)
    """
    # Создаём сайт
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    # Импортируем график с этапами
    csv_content = (
        "name,start,end\n"
        "Устройство свай,2024-01-01,2024-01-10\n"
        "Разработка котлована,2024-01-11,2024-01-20\n"
        "Отделка фасада,2024-01-21,2024-01-31\n"
    ).encode()

    import_resp = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )
    schedule_id = import_resp.json()["id"]

    return site_id, schedule_id


class RecordingStatusRecalculator:
    """Фейковый рекалькулятор, записывающий вызовы."""

    def __init__(self) -> None:
        self.calls: list[uuid.UUID] = []

    async def recalculate(self, site_id: uuid.UUID) -> None:
        """Записать вызов."""
        self.calls.append(site_id)


async def test_get_equipment_types_returns_200_with_list(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """GET /equipment-types возвращает 200 и список всех типов оборудования."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    response = await client.get("/equipment-types")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 20

    # Проверить структуру первого элемента
    first = data[0]
    assert "id" in first
    assert "code" in first
    assert "title" in first
    assert "synonyms" in first
    assert isinstance(first["synonyms"], list)


async def test_get_methodology_returns_200_with_rules(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """GET /sites/{site_id}/methodology возвращает 200 и правила с наборами."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    site_id, _ = await create_site_with_schedule(client, container)

    # Получаем методологию
    response = await client.get(f"/sites/{site_id}/methodology")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3  # Три этапа

    # Проверяем структуру правила
    rules_by_stage_name = {r.get("stage_name"): r for r in data}

    # Устройство свай должно быть проверяемым с 2 наборами
    piles_rule = rules_by_stage_name.get("Устройство свай")
    assert piles_rule is not None
    assert piles_rule["is_verifiable"] is True
    assert piles_rule["unverifiable_reason"] is None
    assert len(piles_rule["sets"]) == 2

    # Первый набор (буровая установка) должен содержать ГЭСН
    first_set = piles_rule["sets"][0]
    assert len(first_set["requirements"]) > 0

    # Ищем требование с ГЭСН кодом 05-01-079-01
    has_gesn = any(req.get("gesn_code") == "05-01-079-01" for req in first_set["requirements"])
    assert has_gesn, "Первый набор должен содержать требование с ГЭСН 05-01-079-01"

    # Разработка котлована должна быть проверяемой
    excavation_rule = rules_by_stage_name.get("Разработка котлована")
    assert excavation_rule is not None
    assert excavation_rule["is_verifiable"] is True

    # Отделка фасада не должна быть проверяемой (нет совпадения в defaults)
    facade_rule = rules_by_stage_name.get("Отделка фасада")
    assert facade_rule is not None
    assert facade_rule["is_verifiable"] is False
    assert facade_rule["unverifiable_reason"] is not None


async def test_get_methodology_for_nonexistent_site_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """GET /sites/{site_id}/methodology для несуществующего сайта возвращает 404."""
    await seed_stand_user(container)

    fake_site_id = uuid.uuid4()
    response = await client.get(f"/sites/{fake_site_id}/methodology")

    assert response.status_code == 404


async def test_get_methodology_without_schedule_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """GET /sites/{site_id}/methodology без загруженного графика возвращает 404."""
    await seed_stand_user(container)

    # Создаём сайт БЕЗ графика
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    response = await client.get(f"/sites/{site_id}/methodology")

    assert response.status_code == 404
    assert "График не загружен" in response.json()["detail"]


async def test_patch_rule_to_unverifiable_with_reason_returns_200(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """PATCH /sites/{site_id}/methodology/rules/{rule_id} с unverifiable_reason возвращает 200."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    site_id, _ = await create_site_with_schedule(client, container)

    # Получаем правила
    get_resp = await client.get(f"/sites/{site_id}/methodology")
    rules = get_resp.json()

    # Берём первое правило
    rule = rules[0]
    rule_id = rule["id"]

    # Обновляем на unverifiable с причиной
    response = await client.patch(
        f"/sites/{site_id}/methodology/rules/{rule_id}",
        json={"is_verifiable": False, "unverifiable_reason": "Нет оборудования"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_verifiable"] is False
    assert data["unverifiable_reason"] == "Нет оборудования"


async def test_patch_rule_to_unverifiable_without_reason_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """PATCH без reason при unverifiable возвращает 422."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    site_id, _ = await create_site_with_schedule(client, container)

    # Получаем правила
    get_resp = await client.get(f"/sites/{site_id}/methodology")
    rules = get_resp.json()
    rule_id = rules[0]["id"]

    # Обновляем без причины
    response = await client.patch(
        f"/sites/{site_id}/methodology/rules/{rule_id}",
        json={"is_verifiable": False},
    )

    assert response.status_code == 422


async def test_patch_rule_to_verifiable_clears_reason(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """PATCH на verifiable=True очищает reason."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    site_id, _ = await create_site_with_schedule(client, container)

    # Получаем правила
    get_resp = await client.get(f"/sites/{site_id}/methodology")
    rules = get_resp.json()
    rule_id = rules[2]["id"]  # Возьмём правило "Отделка фасада" (unverifiable)

    # Обновляем на verifiable
    response = await client.patch(
        f"/sites/{site_id}/methodology/rules/{rule_id}",
        json={"is_verifiable": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_verifiable"] is True
    assert data["unverifiable_reason"] is None


async def test_patch_nonexistent_rule_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """PATCH несуществующего правила возвращает 404."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    site_id, _ = await create_site_with_schedule(client, container)
    fake_rule_id = uuid.uuid4()

    response = await client.patch(
        f"/sites/{site_id}/methodology/rules/{fake_rule_id}",
        json={"is_verifiable": False, "unverifiable_reason": "Test"},
    )

    assert response.status_code == 404


async def test_post_set_with_normative_and_logical_returns_201(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """POST набора с нормативным и логическим требованием возвращает 201."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    site_id, _ = await create_site_with_schedule(client, container)

    # Получаем правила
    get_resp = await client.get(f"/sites/{site_id}/methodology")
    rules = get_resp.json()
    rule_id = rules[2]["id"]  # Берём "Отделка фасада" (unverifiable)

    # Получаем ID типа оборудования для экскаватора
    eq_resp = await client.get("/equipment-types")
    equipment_types = eq_resp.json()
    excavator_id = next(eq["id"] for eq in equipment_types if eq["code"] == "excavator_crawler")

    # Создаём набор требований
    set_data = {
        "requirements": [
            {
                "equipment_type_id": str(excavator_id),
                "min_count": 1,
                "obligation": "normative",
                "gesn_code": "05-01-079-01",
            },
            {
                "equipment_type_id": str(excavator_id),
                "min_count": 2,
                "obligation": "logical",
                "source_note": "Второй экскаватор для параллельных работ",
            },
        ]
    }

    response = await client.post(
        f"/sites/{site_id}/methodology/rules/{rule_id}/sets",
        json=set_data,
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["position"] >= 0
    assert len(data["requirements"]) == 2


async def test_post_set_logical_only_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """POST набора с только логическими требованиями возвращает 422."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    site_id, _ = await create_site_with_schedule(client, container)

    # Получаем правила и оборудование
    get_resp = await client.get(f"/sites/{site_id}/methodology")
    rules = get_resp.json()
    rule_id = rules[0]["id"]

    eq_resp = await client.get("/equipment-types")
    equipment_types = eq_resp.json()
    excavator_id = next(eq["id"] for eq in equipment_types if eq["code"] == "excavator_crawler")

    # Создаём набор только с логическими требованиями
    set_data = {
        "requirements": [
            {
                "equipment_type_id": str(excavator_id),
                "obligation": "logical",
                "source_note": "Только логическое",
            },
        ]
    }

    response = await client.post(
        f"/sites/{site_id}/methodology/rules/{rule_id}/sets",
        json=set_data,
    )

    assert response.status_code == 422
    assert "Логическое требование" in response.json()["detail"]


async def test_post_set_with_unknown_equipment_type_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """POST с неизвестным equipment_type_id возвращает 422."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    site_id, _ = await create_site_with_schedule(client, container)

    get_resp = await client.get(f"/sites/{site_id}/methodology")
    rules = get_resp.json()
    rule_id = rules[0]["id"]

    fake_equipment_id = uuid.uuid4()

    set_data = {
        "requirements": [
            {
                "equipment_type_id": str(fake_equipment_id),
                "obligation": "normative",
                "gesn_code": "05-01-079-01",
            },
        ]
    }

    response = await client.post(
        f"/sites/{site_id}/methodology/rules/{rule_id}/sets",
        json=set_data,
    )

    assert response.status_code == 422


async def test_post_set_with_min_count_zero_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """POST с min_count < 1 возвращает 422."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    site_id, _ = await create_site_with_schedule(client, container)

    get_resp = await client.get(f"/sites/{site_id}/methodology")
    rules = get_resp.json()
    rule_id = rules[0]["id"]

    eq_resp = await client.get("/equipment-types")
    equipment_types = eq_resp.json()
    excavator_id = next(eq["id"] for eq in equipment_types if eq["code"] == "excavator_crawler")

    set_data = {
        "requirements": [
            {
                "equipment_type_id": str(excavator_id),
                "min_count": 0,
                "obligation": "normative",
                "gesn_code": "05-01-079-01",
            },
        ]
    }

    response = await client.post(
        f"/sites/{site_id}/methodology/rules/{rule_id}/sets",
        json=set_data,
    )

    assert response.status_code == 422


async def test_post_set_without_source_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """POST без gesn_code и source_note возвращает 422."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    site_id, _ = await create_site_with_schedule(client, container)

    get_resp = await client.get(f"/sites/{site_id}/methodology")
    rules = get_resp.json()
    rule_id = rules[0]["id"]

    eq_resp = await client.get("/equipment-types")
    equipment_types = eq_resp.json()
    excavator_id = next(eq["id"] for eq in equipment_types if eq["code"] == "excavator_crawler")

    set_data = {
        "requirements": [
            {
                "equipment_type_id": str(excavator_id),
                "min_count": 1,
                "obligation": "normative",
            },
        ]
    }

    response = await client.post(
        f"/sites/{site_id}/methodology/rules/{rule_id}/sets",
        json=set_data,
    )

    assert response.status_code == 422


async def test_put_set_replaces_requirements_returns_200(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """PUT /sites/{site_id}/methodology/sets/{set_id} заменяет требования и возвращает 200."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    site_id, _ = await create_site_with_schedule(client, container)

    # Получаем первое правило с наборами
    get_resp = await client.get(f"/sites/{site_id}/methodology")
    rules = get_resp.json()

    # Ищем правило с наборами
    rule_with_sets = next(r for r in rules if len(r["sets"]) > 0)
    set_id = rule_with_sets["sets"][0]["id"]

    # Получаем оборудование
    eq_resp = await client.get("/equipment-types")
    equipment_types = eq_resp.json()
    truck_id = next(eq["id"] for eq in equipment_types if eq["code"] == "dump_truck")

    # Заменяем требования
    set_data = {
        "requirements": [
            {
                "equipment_type_id": str(truck_id),
                "min_count": 3,
                "obligation": "normative",
                "gesn_code": "05-01-080-01",
            },
        ]
    }

    response = await client.put(
        f"/sites/{site_id}/methodology/sets/{set_id}",
        json=set_data,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["requirements"]) == 1
    assert data["requirements"][0]["min_count"] == 3


async def test_delete_set_returns_204(client: AsyncClient, container: AsyncContainer) -> None:
    """DELETE /sites/{site_id}/methodology/sets/{set_id} возвращает 204."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    site_id, _ = await create_site_with_schedule(client, container)

    # Получаем первое правило с наборами
    get_resp = await client.get(f"/sites/{site_id}/methodology")
    rules = get_resp.json()
    rule_with_sets = next(r for r in rules if len(r["sets"]) > 1)
    initial_set_count = len(rule_with_sets["sets"])
    set_id = rule_with_sets["sets"][0]["id"]

    # Удаляем набор
    response = await client.delete(f"/sites/{site_id}/methodology/sets/{set_id}")

    assert response.status_code == 204

    # Проверяем, что набор удалён
    get_resp = await client.get(f"/sites/{site_id}/methodology")
    rules = get_resp.json()
    updated_rule = next(r for r in rules if r["id"] == rule_with_sets["id"])
    assert len(updated_rule["sets"]) == initial_set_count - 1


async def test_delete_nonexistent_set_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """DELETE несуществующего набора возвращает 404."""
    await seed_stand_user(container)
    await seed_equipment_types(container)

    site_id, _ = await create_site_with_schedule(client, container)

    fake_set_id = uuid.uuid4()

    response = await client.delete(f"/sites/{site_id}/methodology/sets/{fake_set_id}")

    assert response.status_code == 404


async def test_status_recalculator_called_on_mutation() -> None:
    """StatusRecalculator вызывается при каждой мутации методологии.

    Проверяет: GET не вызывает, PATCH вызывает один раз, POST valid вызывает дважды,
    POST invalid (422) не вызывает, DELETE вызывает трижды.
    """

    # Создаём фейковый рекалькулятор
    recording_recalculator = RecordingStatusRecalculator()

    # Создаём test-specific контейнер с recording fake
    class TestAppProvider(Provider):
        scope = Scope.APP

        @provide
        def settings(self) -> Settings:
            return get_settings()

    class TestDatabaseProvider(Provider):
        scope = Scope.APP

        @provide
        async def engine(self) -> AsyncIterable[AsyncEngine]:
            engine = create_async_engine(
                "sqlite+aiosqlite:///:memory:",
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            yield engine
            await engine.dispose()

        @provide
        def sessionmaker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
            return async_sessionmaker(engine, expire_on_commit=False)

        @provide(scope=Scope.REQUEST)
        async def session(
            self, maker: async_sessionmaker[AsyncSession]
        ) -> AsyncIterable[AsyncSession]:
            async with maker() as session:
                yield session

    class RecalculatorProvider(Provider):
        scope = Scope.APP

        @provide(provides=StatusRecalculator)
        def provide_recalculator(self) -> StatusRecalculator:
            return recording_recalculator

    # Создаём контейнер с переопределённым рекалькулятором
    test_container = make_async_container(
        TestAppProvider(),
        TestDatabaseProvider(),
        UserProvider(),
        SiteProvider(),
        ScheduleProvider(),
        MethodologyProvider(),
        RecalculatorProvider(),  # Переопределяет MethodologyProvider's recalculator
        UtilityProvider(),
    )

    # Создаём приложение и клиент
    app = create_app(test_container)
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test/api")

    async with test_container:
        async with client:
            # Инициализируем пользователя и оборудование
            await seed_stand_user(test_container)
            await seed_equipment_types(test_container)

            # Создаём сайт и график
            site_id, _ = await create_site_with_schedule(client, test_container)
            site_id = uuid.UUID(site_id) if isinstance(site_id, str) else site_id

            # GET /sites/{site_id}/methodology не должен вызывать рекалькулятор
            get_resp = await client.get(f"/sites/{site_id}/methodology")
            assert get_resp.status_code == 200
            rules = get_resp.json()
            assert len(recording_recalculator.calls) == 0, "GET должен не вызывать рекалькулятор"

            rule_id = rules[2]["id"]  # Берём "Отделка фасада"

            # PATCH правила -> ровно 1 вызов
            patch_resp = await client.patch(
                f"/sites/{site_id}/methodology/rules/{rule_id}",
                json={"is_verifiable": False, "unverifiable_reason": "Test reason"},
            )
            assert patch_resp.status_code == 200
            assert len(recording_recalculator.calls) == 1
            assert recording_recalculator.calls[0] == site_id, (
                f"Expected {site_id}, got {recording_recalculator.calls[0]}"
            )

            # Получаем оборудование для POST
            eq_resp = await client.get("/equipment-types")
            equipment_types = eq_resp.json()
            excavator_id = next(
                eq["id"] for eq in equipment_types if eq["code"] == "excavator_crawler"
            )

            # POST valid set -> ещё 1 вызов (всего 2)
            post_resp = await client.post(
                f"/sites/{site_id}/methodology/rules/{rule_id}/sets",
                json={
                    "requirements": [
                        {
                            "equipment_type_id": str(excavator_id),
                            "obligation": "normative",
                            "gesn_code": "05-01-079-01",
                        },
                    ]
                },
            )
            assert post_resp.status_code == 201
            assert len(recording_recalculator.calls) == 2
            assert recording_recalculator.calls[1] == site_id

            set_id = post_resp.json()["id"]

            # POST invalid (logical-only) -> 422, не вызывает рекалькулятор (всё ещё 2)
            invalid_post_resp = await client.post(
                f"/sites/{site_id}/methodology/rules/{rule_id}/sets",
                json={
                    "requirements": [
                        {
                            "equipment_type_id": str(excavator_id),
                            "obligation": "logical",
                            "source_note": "Only logical",
                        },
                    ]
                },
            )
            assert invalid_post_resp.status_code == 422
            assert len(recording_recalculator.calls) == 2, "422 не должен вызывать рекалькулятор"

            # DELETE set -> ещё 1 вызов (всего 3)
            delete_resp = await client.delete(f"/sites/{site_id}/methodology/sets/{set_id}")
            assert delete_resp.status_code == 204
            assert len(recording_recalculator.calls) == 3
            assert recording_recalculator.calls[2] == site_id
