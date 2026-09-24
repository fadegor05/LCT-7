"""HTTP-контракт стендового пользователя."""

from dishka import AsyncContainer
from httpx import AsyncClient

from app.domains.user.service import STAND_USER_DEFAULT_NAME, STAND_USER_ID, UserService


async def seed(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


async def test_get_me_returns_stand_user(client: AsyncClient, container: AsyncContainer) -> None:
    await seed(container)

    response = await client.get("/users/me")

    assert response.status_code == 200
    assert response.json()["id"] == str(STAND_USER_ID)
    assert response.json()["full_name"] == STAND_USER_DEFAULT_NAME


async def test_me_response_has_no_legacy_fields(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Ни пароля, ни роли, ни email: этих понятий в MVP нет."""
    await seed(container)

    response = await client.get("/users/me")

    assert set(response.json()) == {"id", "full_name", "created_at"}


async def test_patch_me_updates_full_name(client: AsyncClient, container: AsyncContainer) -> None:
    await seed(container)

    patched = await client.patch("/users/me", json={"full_name": "Иванов И. И."})
    reread = await client.get("/users/me")

    assert patched.status_code == 200
    assert reread.json()["full_name"] == "Иванов И. И."


async def test_patch_me_rejects_blank_and_overlong_name(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """ФИО печатается в отчёте дословно — пустая строка и 300 символов недопустимы."""
    await seed(container)

    blank = await client.patch("/users/me", json={"full_name": "   "})
    overlong = await client.patch("/users/me", json={"full_name": "и" * 300})

    assert blank.status_code == 422
    assert overlong.status_code == 422


async def test_get_me_without_seed_returns_503(client: AsyncClient) -> None:
    """Миграции накатаны, seed не выполнялся — понятная 503, а не 500."""
    response = await client.get("/users/me")

    assert response.status_code == 503
    assert "не инициализирован" in response.json()["detail"]
