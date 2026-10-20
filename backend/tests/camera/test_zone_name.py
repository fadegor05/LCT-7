"""Название рабочей зоны камеры: необязательное, в API и в базе.

Название попадает в тексты отклонений; пустое и из одних пробелов хранится как null.
"""

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient

from app.domains.user.service import UserService

ZONE = [[0.1, 0.2], [0.9, 0.2], [0.9, 0.95], [0.1, 0.95]]


@pytest.fixture
async def stand_client(client: AsyncClient, container: AsyncContainer) -> AsyncClient:
    async with container() as request_container:
        await (await request_container.get(UserService)).ensure_stand_user()
    return client


async def _site(client: AsyncClient) -> str:
    return (await client.post("/sites", json={"name": "Объект"})).json()["id"]


async def _camera(client: AsyncClient, site: str, **body) -> dict:
    r = await client.post(f"/sites/{site}/cameras", json={"name": "К-1", **body})
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_with_zone_name_returns_it_in_create_and_list(
    stand_client: AsyncClient,
) -> None:
    site = await _site(stand_client)

    created = await _camera(stand_client, site, zone_name="Сборочный цех")

    assert created["zone_name"] == "Сборочный цех"
    listed = (await stand_client.get(f"/sites/{site}/cameras")).json()
    assert listed[0]["zone_name"] == "Сборочный цех"


async def test_create_without_zone_name_is_null(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)

    created = await _camera(stand_client, site)

    assert created["zone_name"] is None


async def test_patch_sets_zone_name(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)
    url = f"/sites/{site}/cameras/{camera['id']}"

    r = await stand_client.patch(url, json={"zone_name": "Склад"})

    assert r.status_code == 200, r.text
    assert r.json()["zone_name"] == "Склад"


async def test_patch_null_clears_zone_name(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, zone_name="Склад")
    url = f"/sites/{site}/cameras/{camera['id']}"

    r = await stand_client.patch(url, json={"zone_name": None})

    assert r.status_code == 200, r.text
    assert r.json()["zone_name"] is None


async def test_patch_without_zone_name_keeps_it(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, zone_name="Склад", zone=ZONE)
    url = f"/sites/{site}/cameras/{camera['id']}"

    r = await stand_client.patch(url, json={"name": "К-2"})

    assert r.status_code == 200, r.text
    assert r.json()["name"] == "К-2"
    assert r.json()["zone_name"] == "Склад"


@pytest.mark.parametrize("blank", ["", "   "])
async def test_blank_zone_name_is_stored_as_null_on_create(
    stand_client: AsyncClient, blank: str
) -> None:
    site = await _site(stand_client)

    created = await _camera(stand_client, site, zone_name=blank)

    assert created["zone_name"] is None


@pytest.mark.parametrize("blank", ["", "   "])
async def test_blank_zone_name_is_stored_as_null_on_patch(
    stand_client: AsyncClient, blank: str
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, zone_name="Склад")
    url = f"/sites/{site}/cameras/{camera['id']}"

    r = await stand_client.patch(url, json={"zone_name": blank})

    assert r.status_code == 200, r.text
    assert r.json()["zone_name"] is None


async def test_zone_name_is_stripped(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)

    created = await _camera(stand_client, site, zone_name="  Склад  ")

    assert created["zone_name"] == "Склад"


async def test_zone_name_of_100_chars_is_accepted(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)

    created = await _camera(stand_client, site, zone_name="я" * 100)

    assert created["zone_name"] == "я" * 100


async def test_zone_name_over_100_chars_is_422_on_create(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)

    r = await stand_client.post(
        f"/sites/{site}/cameras", json={"name": "К-1", "zone_name": "я" * 101}
    )

    assert r.status_code == 422, r.text


async def test_zone_name_over_100_chars_is_422_on_patch(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, zone_name="Склад")

    r = await stand_client.patch(
        f"/sites/{site}/cameras/{camera['id']}", json={"zone_name": "я" * 101}
    )

    assert r.status_code == 422, r.text
