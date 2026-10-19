"""Модель объекта строительства (docs/DataModel.md §5.2): таблица sites."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domains.site.models import Site
from app.domains.site.repository import SiteRepository
from app.domains.user.models import User


@pytest.mark.asyncio
async def test_site_table_exists(engine: AsyncEngine) -> None:
    """Таблица sites создана в схеме."""
    async with engine.connect() as conn:
        result = await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sites'"
            )
        )
        assert result.scalar() == "sites"


@pytest.mark.asyncio
async def test_site_columns(engine: AsyncEngine) -> None:
    """Колонки соответствуют модели."""
    async with engine.connect() as conn:
        result = await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text("PRAGMA table_info(sites)")
        )
        columns = {row[1] for row in result.all()}
        assert columns == {
            "id",
            "name",
            "address",
            "object_type",
            "workdays",
            "owner_id",
            "created_at",
            "updated_at",
        }


@pytest.mark.asyncio
async def test_site_persists_with_owner(engine: AsyncEngine, container) -> None:
    """Site сохраняется с owner_id и читается обратно с id, created_at, updated_at."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Создаём пользователя-владельца
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        # Создаём объект строительства
        site = Site(
            id=uuid.uuid4(),
            name="Construction Site 1",
            address="123 Main Street",
            owner_id=owner_id,
        )
        session.add(site)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(Site, site.id)
        assert fetched is not None
        assert fetched.id == site.id
        assert fetched.name == "Construction Site 1"
        assert fetched.address == "123 Main Street"
        assert fetched.owner_id == owner_id
        assert fetched.created_at is not None
        assert isinstance(fetched.created_at, datetime)
        assert fetched.updated_at is not None
        assert isinstance(fetched.updated_at, datetime)


@pytest.mark.asyncio
async def test_site_address_nullable(engine: AsyncEngine, container) -> None:
    """address может быть None."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="Jane Doe")
        session.add(owner)

        site = Site(
            id=uuid.uuid4(),
            name="Site Without Address",
            owner_id=owner_id,
        )
        session.add(site)
        await session.commit()

        fetched = await session.get(Site, site.id)
        assert fetched is not None
        assert fetched.address is None


@pytest.mark.asyncio
async def test_site_repository_list_by_owner(engine: AsyncEngine, container) -> None:
    """SiteRepository.list_by_owner возвращает сайты владельца.

    Упорядочены по created_at desc.
    """
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Создаём двух пользователей
        owner1_id = uuid.uuid4()
        owner2_id = uuid.uuid4()
        owner1 = User(id=owner1_id, full_name="Owner 1")
        owner2 = User(id=owner2_id, full_name="Owner 2")
        session.add(owner1)
        session.add(owner2)

        # Создаём сайты для каждого владельца
        # Для owner1: 2 сайта
        site1_id = uuid.uuid4()
        site2_id = uuid.uuid4()
        site3_id = uuid.uuid4()

        site1 = Site(id=site1_id, name="Site 1 - Owner 1", owner_id=owner1_id)
        site2 = Site(id=site2_id, name="Site 2 - Owner 1", owner_id=owner1_id)
        # Для owner2: 1 сайт
        site3 = Site(id=site3_id, name="Site 3 - Owner 2", owner_id=owner2_id)

        session.add(site1)
        session.add(site2)
        session.add(site3)
        await session.commit()

        # Используем репозиторий
        repo = SiteRepository(session)

        # Получаем сайты owner1
        owner1_sites = await repo.list_by_owner(owner1_id)
        assert len(owner1_sites) == 2
        assert all(site.owner_id == owner1_id for site in owner1_sites)

        # Получаем сайты owner2
        owner2_sites = await repo.list_by_owner(owner2_id)
        assert len(owner2_sites) == 1
        assert owner2_sites[0].owner_id == owner2_id

        # Проверяем, что сайты упорядочены по created_at desc (новые первыми)
        # В SQLite если timestamps совпадают, проверяем порядок вставки
        # Вставляем с явным временем создания
        await session.rollback()

    async with maker() as session:
        owner1_id = uuid.uuid4()
        owner1 = User(id=owner1_id, full_name="Owner 1")
        session.add(owner1)

        # Создаём 3 сайта с явно установленным created_at
        now = datetime.now(UTC)
        site_old_id = uuid.uuid4()
        site_mid_id = uuid.uuid4()
        site_new_id = uuid.uuid4()

        site_old = Site(
            id=site_old_id,
            name="Old Site",
            owner_id=owner1_id,
            created_at=now - timedelta(hours=2),
        )
        site_mid = Site(
            id=site_mid_id,
            name="Mid Site",
            owner_id=owner1_id,
            created_at=now - timedelta(hours=1),
        )
        site_new = Site(
            id=site_new_id,
            name="New Site",
            owner_id=owner1_id,
            created_at=now,
        )

        session.add(site_old)
        session.add(site_mid)
        session.add(site_new)
        await session.commit()

        repo = SiteRepository(session)
        sites = await repo.list_by_owner(owner1_id)

        # Проверяем порядок: новые первыми
        assert len(sites) == 3
        assert sites[0].id == site_new_id
        assert sites[1].id == site_mid_id
        assert sites[2].id == site_old_id
