"""Стендовая идентичность: один seed-пользователь и контракт CurrentUser для других доменов."""

import pytest
from dishka import AsyncContainer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.user.models import User
from app.domains.user.provider import CurrentUser
from app.domains.user.service import STAND_USER_DEFAULT_NAME, STAND_USER_ID, UserService
from app.plugins.exceptions import AppError


async def test_ensure_stand_user_creates_row(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        user = await service.ensure_stand_user()

    assert user.id == STAND_USER_ID
    assert user.full_name == STAND_USER_DEFAULT_NAME


async def test_ensure_stand_user_is_idempotent(container: AsyncContainer) -> None:
    """Seed выполняется при каждом старте — второй прогон не должен дублировать строку."""
    for _ in range(2):
        async with container() as request_container:
            service = await request_container.get(UserService)
            await service.ensure_stand_user()

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        total = await session.scalar(select(func.count()).select_from(User))

    assert total == 1


async def test_ensure_stand_user_keeps_edited_name(container: AsyncContainer) -> None:
    """Перезапуск приложения не откатывает ФИО, заданное инженером."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()
        await service.rename("Иванов И. И.")

    async with container() as request_container:
        service = await request_container.get(UserService)
        user = await service.ensure_stand_user()

    assert user.full_name == "Иванов И. И."


async def test_current_user_resolves_for_other_domains(container: AsyncContainer) -> None:
    """Контракт для доменов site/observation/...: личность берётся из DI, а не из домена user."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()

    async with container() as request_container:
        user = await request_container.get(CurrentUser)

    assert user.id == STAND_USER_ID


async def test_current_user_missing_row_raises_503(container: AsyncContainer) -> None:
    """База накатана миграциями, но не засеяна: понятная 503 вместо падения на None."""
    with pytest.raises(AppError) as exc_info:
        async with container() as request_container:
            await request_container.get(CurrentUser)

    assert exc_info.value.status_code == 503
