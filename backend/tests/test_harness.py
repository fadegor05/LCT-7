"""Проверка тестового каркаса: приложение поднимается на in-memory SQLite."""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_health_answers(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_schema_survives_two_connections(engine: AsyncEngine) -> None:
    """StaticPool: второе соединение видит ту же базу, а не пустую."""
    async with engine.connect() as connection:
        first = await connection.scalar(
            text("SELECT count(*) FROM sqlite_master WHERE type = 'table'")
        )
    async with engine.connect() as connection:
        second = await connection.scalar(
            text("SELECT count(*) FROM sqlite_master WHERE type = 'table'")
        )

    assert first == second
    assert first > 0
