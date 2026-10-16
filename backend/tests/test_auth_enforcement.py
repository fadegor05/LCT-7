"""Авторизация на реальном UserProvider: токены, 401 на защищённых роутах, изоляция, CLI."""

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from dishka import AsyncContainer
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli import create_user
from app.core.settings import DEFAULT_AUTH_SECRET_KEY, AuthSettings, Settings, check_auth_secret
from app.domains.user.provider import UserProvider
from app.domains.user.repository import UserRepository
from app.domains.user.security import create_token, decode_token, verify_password
from app.domains.user.service import UserService
from app.main import create_app
from app.plugins.exceptions import AppError
from tests.conftest import _make_container

PASSWORD = "correct horse battery"


@pytest.fixture
async def auth_container(tmp_path: Path) -> AsyncIterator[AsyncContainer]:
    """Контейнер с РЕАЛЬНЫМ UserProvider: CurrentUser берётся из токена, а не из стенда."""
    container = _make_container(tmp_path, user_provider=UserProvider())
    yield container
    await container.close()


@pytest.fixture
async def auth_client(auth_container: AsyncContainer) -> AsyncIterator[AsyncClient]:
    app = create_app(auth_container)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api") as client:
        yield client


@pytest.fixture
async def auth_settings(auth_container: AsyncContainer) -> AuthSettings:
    return (await auth_container.get(Settings)).auth


async def _register(container: AsyncContainer, login: str) -> None:
    maker = await container.get(async_sessionmaker[AsyncSession])
    await create_user(maker, login, None, PASSWORD)


async def _login(client: AsyncClient, login: str) -> dict[str, str]:
    response = await client.post("/auth/login", json={"login": login, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class TestProtectedRoutes:
    async def test_no_token_is_401(self, auth_client: AsyncClient) -> None:
        response = await auth_client.get("/sites")

        assert response.status_code == 401
        assert response.json()["detail"] == "Требуется авторизация"

    async def test_garbage_token_is_401(self, auth_client: AsyncClient) -> None:
        response = await auth_client.get("/sites", headers={"Authorization": "Bearer nonsense"})

        assert response.status_code == 401

    async def test_wrong_scheme_is_401(self, auth_client: AsyncClient) -> None:
        response = await auth_client.get("/sites", headers={"Authorization": "Basic abc"})

        assert response.status_code == 401

    async def test_expired_token_is_401(
        self, auth_client: AsyncClient, auth_container: AsyncContainer, auth_settings: AuthSettings
    ) -> None:
        await _register(auth_container, "anna")
        user_id = await _user_id(auth_container, "anna")
        expired = create_token(user_id, auth_settings.model_copy(update={"token_ttl_minutes": -5}))

        response = await auth_client.get("/sites", headers={"Authorization": f"Bearer {expired}"})

        assert response.status_code == 401

    async def test_token_signed_with_other_secret_is_401(
        self, auth_client: AsyncClient, auth_container: AsyncContainer, auth_settings: AuthSettings
    ) -> None:
        await _register(auth_container, "anna")
        user_id = await _user_id(auth_container, "anna")
        forged = create_token(
            user_id,
            auth_settings.model_copy(update={"secret_key": "another-secret-of-32-bytes-or-more!"}),
        )

        response = await auth_client.get("/sites", headers={"Authorization": f"Bearer {forged}"})

        assert response.status_code == 401

    async def test_token_of_missing_user_is_401(
        self, auth_client: AsyncClient, auth_settings: AuthSettings
    ) -> None:
        ghost = create_token(uuid.uuid4(), auth_settings)

        response = await auth_client.get("/sites", headers={"Authorization": f"Bearer {ghost}"})

        assert response.status_code == 401

    async def test_valid_token_is_200(
        self, auth_client: AsyncClient, auth_container: AsyncContainer
    ) -> None:
        await _register(auth_container, "anna")
        headers = await _login(auth_client, "anna")

        response = await auth_client.get("/sites", headers=headers)

        assert response.status_code == 200
        assert response.json() == []

    async def test_users_me_returns_the_logged_in_user(
        self, auth_client: AsyncClient, auth_container: AsyncContainer
    ) -> None:
        await _register(auth_container, "anna")
        headers = await _login(auth_client, "anna")

        response = await auth_client.get("/users/me", headers=headers)

        assert response.status_code == 200
        assert response.json()["login"] == "anna"

    async def test_health_and_login_stay_public(self, auth_client: AsyncClient) -> None:
        health = await auth_client.get("/health")
        login = await auth_client.post("/auth/login", json={"login": "x", "password": "y"})

        assert health.status_code == 200
        # 401 из-за неверных данных, а не из-за отсутствия токена: тело — про логин/пароль.
        assert login.status_code == 401
        assert login.json()["detail"] == "Неверный логин или пароль"


class TestSiteIsolation:
    async def test_user_does_not_see_foreign_site(
        self, auth_client: AsyncClient, auth_container: AsyncContainer
    ) -> None:
        await _register(auth_container, "anna")
        await _register(auth_container, "boris")
        anna = await _login(auth_client, "anna")
        boris = await _login(auth_client, "boris")

        created = await auth_client.post("/sites", json={"name": "Объект Анны"}, headers=anna)
        assert created.status_code == 201
        site_id = created.json()["id"]

        foreign = await auth_client.get(f"/sites/{site_id}", headers=boris)
        boris_list = await auth_client.get("/sites", headers=boris)
        own = await auth_client.get(f"/sites/{site_id}", headers=anna)

        assert foreign.status_code == 404
        assert boris_list.json() == []
        assert own.status_code == 200


class TestTokens:
    def test_round_trip(self) -> None:
        settings = AuthSettings(secret_key="k" * 32)
        user_id = uuid.uuid4()

        assert decode_token(create_token(user_id, settings), settings) == user_id

    def test_tampered_token_is_rejected(self) -> None:
        settings = AuthSettings(secret_key="k" * 32)
        token = create_token(uuid.uuid4(), settings)

        with pytest.raises(AppError) as error:
            decode_token(token[:-2] + "xx", settings)

        assert error.value.status_code == 401


class TestSeedCredentials:
    async def _service(self, container: AsyncContainer, settings: AuthSettings) -> UserService:
        session = await container.get(AsyncSession)
        return UserService(UserRepository(session), session, settings)

    async def test_seed_sets_login_and_password(self, auth_container: AsyncContainer) -> None:
        async with auth_container() as scope:
            service = await self._service(
                scope, AuthSettings(seed_login="Boss", seed_password="seed-password")
            )
            user = await service.ensure_stand_user()
            await service.ensure_seed_credentials()

        assert user.login == "boss"
        assert user.password_hash is not None
        assert await verify_password("seed-password", user.password_hash)

    async def test_seed_never_overwrites_existing_credentials(
        self, auth_container: AsyncContainer
    ) -> None:
        async with auth_container() as scope:
            first = await self._service(
                scope, AuthSettings(seed_login="boss", seed_password="first-password")
            )
            await first.ensure_stand_user()
            await first.ensure_seed_credentials()
            second = await self._service(
                scope, AuthSettings(seed_login="other", seed_password="second-password")
            )
            await second.ensure_seed_credentials()
            user = await second.get_current()

        assert user.login == "boss"
        assert user.password_hash is not None
        assert await verify_password("first-password", user.password_hash)

    async def test_seed_without_settings_leaves_user_without_login(
        self, auth_container: AsyncContainer
    ) -> None:
        async with auth_container() as scope:
            service = await self._service(scope, AuthSettings())
            user = await service.ensure_stand_user()
            await service.ensure_seed_credentials()

        assert user.login is None


class TestAuthSecretCheck:
    def test_default_secret_in_secure_mode_is_refused(self) -> None:
        settings = Settings(secure=True)

        with pytest.raises(RuntimeError):
            check_auth_secret(settings)

    def test_custom_secret_in_secure_mode_is_ok(self) -> None:
        settings = Settings(secure=True, auth=AuthSettings(secret_key="s" * 40))

        check_auth_secret(settings)

    def test_default_secret_outside_secure_mode_is_ok(self) -> None:
        settings = Settings(secure=False, auth=AuthSettings(secret_key=DEFAULT_AUTH_SECRET_KEY))

        check_auth_secret(settings)


class TestCreateUserCli:
    async def test_creates_user_with_normalized_login_and_hash(
        self, auth_container: AsyncContainer
    ) -> None:
        maker = await auth_container.get(async_sessionmaker[AsyncSession])

        user = await create_user(maker, "  Foreman ", "Иванов И. И.", PASSWORD)

        assert user.login == "foreman"
        assert user.full_name == "Иванов И. И."
        assert user.password_hash is not None
        assert user.password_hash != PASSWORD
        assert await verify_password(PASSWORD, user.password_hash)

    async def test_duplicate_login_is_refused(self, auth_container: AsyncContainer) -> None:
        maker = await auth_container.get(async_sessionmaker[AsyncSession])
        await create_user(maker, "foreman", None, PASSWORD)

        with pytest.raises(AppError):
            await create_user(maker, "FOREMAN", None, PASSWORD)

    async def test_empty_password_is_refused(self, auth_container: AsyncContainer) -> None:
        maker = await auth_container.get(async_sessionmaker[AsyncSession])

        with pytest.raises(AppError):
            await create_user(maker, "foreman", None, "")


async def _user_id(container: AsyncContainer, login: str) -> uuid.UUID:
    async with container() as scope:
        repository = await scope.get(UserRepository)
        user = await repository.get_by_login(login)
    assert user is not None
    return user.id
