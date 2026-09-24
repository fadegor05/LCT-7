"""SiteAccessGuard: require() method."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.site.guard import SiteAccessGuard
from app.domains.site.models import Site
from app.domains.user.models import User
from app.domains.user.service import STAND_USER_ID, UserService
from app.plugins.exceptions import AppError


async def seed(container) -> None:
    """Создаёт стендового пользователя."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


@pytest.mark.asyncio
async def test_guard_require_own_site_succeeds(container) -> None:
    """guard.require() должна вернуть свой сайт."""
    await seed(container)

    # Создаём сайт
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        site = Site(id=uuid.uuid4(), name="My Site", owner_id=STAND_USER_ID)
        session.add(site)
        await session.commit()
        site_id = site.id

    # Проверяем доступ
    async with container() as request_container:
        guard = await request_container.get(SiteAccessGuard)
        fetched = await guard.require(site_id)

    assert fetched.id == site_id
    assert fetched.owner_id == STAND_USER_ID


@pytest.mark.asyncio
async def test_guard_require_foreign_site_raises_404(container) -> None:
    """guard.require() чужого сайта должна поднять 404."""
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

    # Пытаемся получить доступ
    async with container() as request_container:
        guard = await request_container.get(SiteAccessGuard)
        with pytest.raises(AppError) as exc_info:
            await guard.require(foreign_site_id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.message == "Стройка не найдена"


@pytest.mark.asyncio
async def test_guard_require_missing_site_raises_404(container) -> None:
    """guard.require() несуществующего сайта должна поднять 404."""
    await seed(container)

    missing_id = uuid.uuid4()
    async with container() as request_container:
        guard = await request_container.get(SiteAccessGuard)
        with pytest.raises(AppError) as exc_info:
            await guard.require(missing_id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.message == "Стройка не найдена"
