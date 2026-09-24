"""SiteService: create, list, get, update, delete."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.site.models import Site
from app.domains.site.schemas import SiteCreate, SiteUpdate
from app.domains.site.service import SiteService
from app.domains.user.models import User
from app.domains.user.service import STAND_USER_ID, UserService
from app.plugins.exceptions import AppError


async def seed(container) -> None:
    """Создаёт стендового пользователя."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


@pytest.mark.asyncio
async def test_service_create_sets_owner_id_and_persists(container) -> None:
    """create() должна установить owner_id = current_user.id и сохранить в БД."""
    await seed(container)

    async with container() as request_container:
        service = await request_container.get(SiteService)
        created = await service.create(SiteCreate(name="My Site", address="123 Main St"))

    assert created.id is not None
    assert created.name == "My Site"
    assert created.address == "123 Main St"
    assert created.owner_id == STAND_USER_ID

    # Проверяем, что сохранилось в БД
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        fetched = await session.get(Site, created.id)
        assert fetched is not None
        assert fetched.owner_id == STAND_USER_ID


@pytest.mark.asyncio
async def test_service_list_returns_only_own_sites(container) -> None:
    """list() должна вернуть только сайты текущего пользователя."""
    await seed(container)

    # Создаём сайт стендовым пользователем
    async with container() as request_container:
        service = await request_container.get(SiteService)
        own_site = await service.create(SiteCreate(name="Own Site"))

    # Создаём другого пользователя и его сайт напрямую
    other_user_id = uuid.uuid4()
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        other_user = User(id=other_user_id, full_name="Other User")
        session.add(other_user)

        other_site = Site(id=uuid.uuid4(), name="Other Site", owner_id=other_user_id)
        session.add(other_site)
        await session.commit()

    # Проверяем, что list() возвращает только собственный сайт
    async with container() as request_container:
        service = await request_container.get(SiteService)
        sites = await service.list()

    assert len(sites) == 1
    assert sites[0].id == own_site.id


@pytest.mark.asyncio
async def test_service_get_own_site_works(container) -> None:
    """get() должна вернуть свой сайт."""
    await seed(container)

    async with container() as request_container:
        service = await request_container.get(SiteService)
        created = await service.create(SiteCreate(name="My Site"))

    async with container() as request_container:
        service = await request_container.get(SiteService)
        fetched = await service.get(created.id)

    assert fetched.id == created.id
    assert fetched.name == "My Site"


@pytest.mark.asyncio
async def test_service_get_foreign_site_raises_404(container) -> None:
    """get() чужого сайта должна поднять 404 с сообщением 'Стройка не найдена'."""
    await seed(container)

    # Создаём другого пользователя и его сайт
    other_user_id = uuid.uuid4()
    foreign_site_id = uuid.uuid4()
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        other_user = User(id=other_user_id, full_name="Other User")
        session.add(other_user)

        foreign_site = Site(id=foreign_site_id, name="Foreign Site", owner_id=other_user_id)
        session.add(foreign_site)
        await session.commit()

    # Пытаемся получить чужой сайт
    async with container() as request_container:
        service = await request_container.get(SiteService)
        with pytest.raises(AppError) as exc_info:
            await service.get(foreign_site_id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.message == "Стройка не найдена"


@pytest.mark.asyncio
async def test_service_get_missing_site_raises_404(container) -> None:
    """get() несуществующего сайта должна поднять 404."""
    await seed(container)

    missing_id = uuid.uuid4()
    async with container() as request_container:
        service = await request_container.get(SiteService)
        with pytest.raises(AppError) as exc_info:
            await service.get(missing_id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.message == "Стройка не найдена"


@pytest.mark.asyncio
async def test_service_update_changes_only_supplied_fields(container) -> None:
    """update() должна менять только поставленные поля."""
    await seed(container)

    # Создаём сайт
    async with container() as request_container:
        service = await request_container.get(SiteService)
        created = await service.create(SiteCreate(name="Original Name", address="Original Address"))

    # Обновляем только name
    async with container() as request_container:
        service = await request_container.get(SiteService)
        updated = await service.update(created.id, SiteUpdate(name="New Name"))

    assert updated.name == "New Name"
    assert updated.address == "Original Address"

    # Обновляем только address
    async with container() as request_container:
        service = await request_container.get(SiteService)
        updated = await service.update(created.id, SiteUpdate(address="New Address"))

    assert updated.name == "New Name"
    assert updated.address == "New Address"


@pytest.mark.asyncio
async def test_service_update_foreign_site_raises_404(container) -> None:
    """update() чужого сайта должна поднять 404."""
    await seed(container)

    # Создаём чужой сайт
    other_user_id = uuid.uuid4()
    foreign_site_id = uuid.uuid4()
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        other_user = User(id=other_user_id, full_name="Other User")
        session.add(other_user)

        foreign_site = Site(id=foreign_site_id, name="Foreign Site", owner_id=other_user_id)
        session.add(foreign_site)
        await session.commit()

    # Пытаемся обновить чужой сайт
    async with container() as request_container:
        service = await request_container.get(SiteService)
        with pytest.raises(AppError) as exc_info:
            await service.update(foreign_site_id, SiteUpdate(name="Hacked Name"))

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_service_update_explicit_none_name_raises_422(container) -> None:
    """update() с явно переданным name=None должна поднять 422."""
    await seed(container)

    # Создаём сайт
    async with container() as request_container:
        service = await request_container.get(SiteService)
        created = await service.create(SiteCreate(name="My Site"))

    # Пытаемся установить name=None
    async with container() as request_container:
        service = await request_container.get(SiteService)
        with pytest.raises(AppError) as exc_info:
            await service.update(created.id, SiteUpdate(name=None))

    assert exc_info.value.status_code == 422
    assert "name" in exc_info.value.message and "null" in exc_info.value.message


@pytest.mark.asyncio
async def test_service_delete_removes_site(container) -> None:
    """delete() должна удалить сайт."""
    await seed(container)

    # Создаём сайт
    async with container() as request_container:
        service = await request_container.get(SiteService)
        created = await service.create(SiteCreate(name="My Site"))

    site_id = created.id

    # Удаляем сайт
    async with container() as request_container:
        service = await request_container.get(SiteService)
        await service.delete(site_id)

    # Проверяем, что он удалён
    async with container() as request_container:
        service = await request_container.get(SiteService)
        with pytest.raises(AppError) as exc_info:
            await service.get(site_id)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_service_delete_foreign_site_raises_404(container) -> None:
    """delete() чужого сайта должна поднять 404 и не удалить его."""
    await seed(container)

    # Создаём чужой сайт
    other_user_id = uuid.uuid4()
    foreign_site_id = uuid.uuid4()
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        other_user = User(id=other_user_id, full_name="Other User")
        session.add(other_user)

        foreign_site = Site(id=foreign_site_id, name="Foreign Site", owner_id=other_user_id)
        session.add(foreign_site)
        await session.commit()

    # Пытаемся удалить чужой сайт
    async with container() as request_container:
        service = await request_container.get(SiteService)
        with pytest.raises(AppError) as exc_info:
            await service.delete(foreign_site_id)

    assert exc_info.value.status_code == 404

    # Проверяем, что чужой сайт остался
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        still_exists = await session.get(Site, foreign_site_id)
        assert still_exists is not None
