"""Тесты аутентификации и авторизации по логину и паролю."""

from dishka import AsyncContainer
from httpx import AsyncClient

from app.core.rate_limit import SlidingWindowRateLimiter
from app.domains.user.provider import LoginRateLimiter
from app.domains.user.security import hash_password, verify_password
from app.domains.user.service import UserService


async def seed_with_login(container: AsyncContainer, login: str, password: str) -> None:
    """Создать стендового пользователя с логином и паролем."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        user = await service.ensure_stand_user()
        # Вручную устанавливаем логин и пароль
        user.login = login.lower()
        user.password_hash = await hash_password(password)
        await service._session.commit()


class TestLogin:
    """Тесты для POST /auth/login."""

    async def test_login_with_correct_credentials(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """Вход с верным логином и паролем возвращает токен."""
        await seed_with_login(container, "demo", "password123")

        response = await client.post(
            "/auth/login", json={"login": "demo", "password": "password123"}
        )

        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert "user" in body
        assert body["user"]["login"] == "demo"

    async def test_login_with_wrong_password(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """Вход с неверным паролем возвращает 401 с одинаковым сообщением."""
        await seed_with_login(container, "demo", "correct_password")

        response = await client.post(
            "/auth/login", json={"login": "demo", "password": "wrong_password"}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Неверный логин или пароль"

    async def test_login_with_unknown_login(self, client: AsyncClient) -> None:
        """Вход с неизвестным логином возвращает 401."""
        response = await client.post(
            "/auth/login", json={"login": "unknown_user", "password": "password123"}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Неверный логин или пароль"

    async def test_login_case_insensitive(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """Логин работает независимо от регистра."""
        await seed_with_login(container, "DemO", "password123")

        response = await client.post(
            "/auth/login", json={"login": "demo", "password": "password123"}
        )

        assert response.status_code == 200

    async def test_login_with_leading_trailing_spaces(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """Логин с пробелами срезается перед проверкой."""
        await seed_with_login(container, "demo", "password123")

        response = await client.post(
            "/auth/login", json={"login": "  demo  ", "password": "password123"}
        )

        assert response.status_code == 200


class TestRateLimit:
    """Тесты для rate limiting на /auth/login (по логину)."""

    async def test_rate_limit_by_login(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """После превышения лимита попыток входа возвращается 429."""
        await seed_with_login(container, "demo", "password123")

        for _ in range(11):
            response = await client.post(
                "/auth/login", json={"login": "demo", "password": "wrong_password"}
            )

        assert response.status_code == 429
        assert response.json()["code"] == "rate_limited"

    async def test_rate_limit_ignores_x_forwarded_for(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """Лимит ключается по логину, X-Forwarded-For игнорируется."""
        await seed_with_login(container, "demo", "password123")

        for i in range(11):
            response = await client.post(
                "/auth/login",
                json={"login": "demo", "password": "wrong_password"},
                headers={"X-Forwarded-For": f"192.168.1.{i}"},
            )

        assert response.status_code == 429
        assert response.json()["code"] == "rate_limited"

    async def test_login_limiter_separate_from_assistant_limiter(
        self, container: AsyncContainer
    ) -> None:
        """Лимитер логина (LoginRateLimiter) отдельный от лимитера ассистента."""
        async with container() as request_container:
            login_limiter = await request_container.get(LoginRateLimiter)
            assistant_limiter = await request_container.get(SlidingWindowRateLimiter)

        assert login_limiter is not assistant_limiter
        assert isinstance(login_limiter, SlidingWindowRateLimiter)
        assert isinstance(assistant_limiter, SlidingWindowRateLimiter)


class TestSecurity:
    """Тесты для криптографических функций."""

    async def test_hash_password(self) -> None:
        """Hash_password создаёт хеш с использованием argon2."""
        plain = "my_secure_password"
        hashed = await hash_password(plain)

        # Хеш должен быть непустой строкой
        assert len(hashed) > 0
        # Хеш не должен быть равен открытому тексту
        assert hashed != plain
        # Хеш должен содержать маркер argon2
        assert "$argon2" in hashed

    async def test_verify_password_correct(self) -> None:
        """Verify_password возвращает True для верного пароля."""
        plain = "my_secure_password"
        hashed = await hash_password(plain)

        is_valid = await verify_password(plain, hashed)
        assert is_valid is True

    async def test_verify_password_incorrect(self) -> None:
        """Verify_password возвращает False для неверного пароля."""
        plain = "my_secure_password"
        hashed = await hash_password(plain)

        is_valid = await verify_password("wrong_password", hashed)
        assert is_valid is False


class TestSeedCredentials:
    """Тесты для seed credentials."""

    async def test_ensure_seed_credentials_idempotent(self, container: AsyncContainer) -> None:
        """ensure_seed_credentials идемпотентна и не перетирает существующий логин."""
        async with container() as request_container:
            service = await request_container.get(UserService)
            user = await service.ensure_stand_user()

            # Первый вызов
            user.login = "manual_login"
            user.password_hash = await hash_password("manual_password")
            await service._session.commit()

            # Второй вызов (должен ничего не сделать)
            await service.ensure_seed_credentials()

            # Логин не должен измениться
            user = await service.get_current()
            assert user.login == "manual_login"


class TestHealthEndpointsPublic:
    """Тесты что health endpoints остаются публичными."""

    async def test_health_endpoint_public(self, client: AsyncClient) -> None:
        """GET /health доступна без токена."""
        response = await client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_auth_login_endpoint_public(self, client: AsyncClient) -> None:
        """POST /auth/login доступна без токена (естественно)."""
        response = await client.post("/auth/login", json={"login": "test", "password": "test"})

        # Должна вернуться 401 из-за неверных данных, но не из-за отсутствия токена
        assert response.status_code == 401
        assert "Неверный логин или пароль" in response.json()["detail"]
