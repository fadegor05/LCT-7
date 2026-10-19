"""HTTP-контракт ленты уведомлений."""

from dishka import AsyncContainer
from httpx import AsyncClient

from app.domains.user.service import UserService


async def seed(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


async def test_empty_feed(client: AsyncClient, container: AsyncContainer) -> None:
    await seed(container)

    response = await client.get("/notifications")

    assert response.status_code == 200
    assert response.json() == {"items": [], "unread_count": 0}


async def test_test_endpoint_creates_notification(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed(container)

    created = await client.post("/notifications/test", json={})
    feed = await client.get("/notifications")

    assert created.status_code == 201
    assert feed.json()["unread_count"] == 1
    assert feed.json()["items"][0]["title"] == "Тестовое уведомление"


async def test_test_endpoint_accepts_custom_text(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed(container)

    await client.post(
        "/notifications/test",
        json={"title": "Отклонение", "body": "Нет экскаватора", "link": "/sites"},
    )
    feed = await client.get("/notifications")

    item = feed.json()["items"][0]
    assert (item["title"], item["body"], item["link"]) == (
        "Отклонение",
        "Нет экскаватора",
        "/sites",
    )


async def test_read_marks_everything(client: AsyncClient, container: AsyncContainer) -> None:
    await seed(container)
    await client.post("/notifications/test", json={})
    await client.post("/notifications/test", json={})

    marked = await client.post("/notifications/read")
    feed = await client.get("/notifications")

    assert marked.status_code == 200
    assert marked.json() == {"marked": 2}
    assert feed.json()["unread_count"] == 0


async def test_notification_fields_are_exactly_the_contract(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Фронт валидирует ответ zod-схемой — лишние и недостающие поля ломают экран."""
    await seed(container)
    await client.post("/notifications/test", json={})

    item = (await client.get("/notifications")).json()["items"][0]

    assert set(item) == {"id", "type", "title", "body", "link", "read_at", "created_at"}


async def test_limit_is_capped(client: AsyncClient, container: AsyncContainer) -> None:
    """limit приходит из строки запроса — выпрашивать миллион записей нельзя."""
    await seed(container)

    response = await client.get("/notifications", params={"limit": 10_000})

    assert response.status_code == 422
