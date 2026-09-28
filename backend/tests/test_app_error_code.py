"""AppError: поле code в ответе ошибки."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.plugins.exceptions import AppError, register_exception_handlers


@pytest.fixture
def app_with_handlers() -> FastAPI:
    """Минимальное FastAPI приложение с обработчиком ошибок."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/with-code")
    async def with_code() -> None:
        raise AppError("x", status_code=429, code="rate_limited")

    @app.get("/without-code")
    async def without_code() -> None:
        raise AppError("y", status_code=404)

    return app


@pytest.fixture
async def client(app_with_handlers: FastAPI) -> AsyncClient:
    """Асинхронный HTTP-клиент для тестирования приложения."""
    transport = ASGITransport(app=app_with_handlers)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_app_error_with_code(client: AsyncClient) -> None:
    """AppError с кодом включает code в ответ."""
    response = await client.get("/with-code")

    assert response.status_code == 429
    assert response.json() == {"detail": "x", "code": "rate_limited"}


@pytest.mark.asyncio
async def test_app_error_without_code(client: AsyncClient) -> None:
    """AppError без кода не включает поле code в ответ."""
    response = await client.get("/without-code")

    assert response.status_code == 404
    assert response.json() == {"detail": "y"}
    assert "code" not in response.json()
