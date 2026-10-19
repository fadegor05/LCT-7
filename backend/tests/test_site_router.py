"""HTTP-контракт CRUD объектов строительства."""

import uuid

from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.user.service import STAND_USER_ID, UserService


async def seed_stand_user(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


async def test_post_creates_site_with_201(client: AsyncClient, container: AsyncContainer) -> None:
    await seed_stand_user(container)

    response = await client.post(
        "/sites",
        json={"name": "Строка 1", "address": "Москва, ул. Тверская, 1"},
    )

    assert response.status_code == 201
    data = response.json()
    assert set(data.keys()) == {
        "id",
        "name",
        "address",
        "object_type",
        "workdays",
        "owner_id",
        "created_at",
        "updated_at",
    }
    assert data["name"] == "Строка 1"
    assert data["address"] == "Москва, ул. Тверская, 1"
    assert data["owner_id"] == str(STAND_USER_ID)


async def test_post_with_blank_name_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed_stand_user(container)

    response = await client.post("/sites", json={"name": "   "})

    assert response.status_code == 422


async def test_post_with_overlong_address_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed_stand_user(container)

    response = await client.post(
        "/sites",
        json={"name": "Стройка", "address": "x" * 501},
    )

    assert response.status_code == 422


async def test_post_address_null_when_omitted(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed_stand_user(container)

    response = await client.post("/sites", json={"name": "Стройка без адреса"})

    assert response.status_code == 201
    assert response.json()["address"] is None


async def test_get_list_returns_created_sites(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed_stand_user(container)

    # Create two sites
    site1_resp = await client.post("/sites", json={"name": "Site 1"})
    site2_resp = await client.post("/sites", json={"name": "Site 2"})

    # Get list
    list_resp = await client.get("/sites")

    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) == 2
    ids = {site["id"] for site in data}
    assert site1_resp.json()["id"] in ids
    assert site2_resp.json()["id"] in ids


async def test_get_by_id_returns_site(client: AsyncClient, container: AsyncContainer) -> None:
    await seed_stand_user(container)

    site_resp = await client.post("/sites", json={"name": "Test Site", "address": "Test Address"})
    site_id = site_resp.json()["id"]

    get_resp = await client.get(f"/sites/{site_id}")

    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == site_id
    assert data["name"] == "Test Site"
    assert data["address"] == "Test Address"


async def test_patch_name_only_keeps_address(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed_stand_user(container)

    site_resp = await client.post(
        "/sites",
        json={"name": "Original Name", "address": "Original Address"},
    )
    site_id = site_resp.json()["id"]

    patch_resp = await client.patch(f"/sites/{site_id}", json={"name": "Updated Name"})

    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["name"] == "Updated Name"
    assert data["address"] == "Original Address"


async def test_patch_address_only_keeps_name(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed_stand_user(container)

    site_resp = await client.post(
        "/sites",
        json={"name": "Original Name", "address": "Original Address"},
    )
    site_id = site_resp.json()["id"]

    patch_resp = await client.patch(f"/sites/{site_id}", json={"address": "Updated Address"})

    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["name"] == "Original Name"
    assert data["address"] == "Updated Address"


async def test_patch_null_name_returns_422(client: AsyncClient, container: AsyncContainer) -> None:
    await seed_stand_user(container)

    site_resp = await client.post("/sites", json={"name": "Site"})
    site_id = site_resp.json()["id"]

    patch_resp = await client.patch(f"/sites/{site_id}", json={"name": None})

    assert patch_resp.status_code == 422


async def test_patch_blank_name_returns_422(client: AsyncClient, container: AsyncContainer) -> None:
    await seed_stand_user(container)

    site_resp = await client.post("/sites", json={"name": "Site"})
    site_id = site_resp.json()["id"]

    patch_resp = await client.patch(f"/sites/{site_id}", json={"name": "   "})

    assert patch_resp.status_code == 422


async def test_delete_returns_204_with_empty_body(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed_stand_user(container)

    site_resp = await client.post("/sites", json={"name": "Site to Delete"})
    site_id = site_resp.json()["id"]

    delete_resp = await client.delete(f"/sites/{site_id}")

    assert delete_resp.status_code == 204
    assert delete_resp.content == b""


async def test_get_deleted_site_returns_404(client: AsyncClient, container: AsyncContainer) -> None:
    await seed_stand_user(container)

    site_resp = await client.post("/sites", json={"name": "Site to Delete"})
    site_id = site_resp.json()["id"]

    await client.delete(f"/sites/{site_id}")
    get_resp = await client.get(f"/sites/{site_id}")

    assert get_resp.status_code == 404
    assert "Стройка не найдена" in get_resp.json()["detail"]


async def test_get_nonexistent_site_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed_stand_user(container)

    response = await client.get(f"/sites/{uuid.uuid4()}")

    assert response.status_code == 404
    assert "Стройка не найдена" in response.json()["detail"]


async def test_patch_nonexistent_site_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed_stand_user(container)

    response = await client.patch(f"/sites/{uuid.uuid4()}", json={"name": "Updated"})

    assert response.status_code == 404
    assert "Стройка не найдена" in response.json()["detail"]


async def test_delete_nonexistent_site_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed_stand_user(container)

    response = await client.delete(f"/sites/{uuid.uuid4()}")

    assert response.status_code == 404
    assert "Стройка не найдена" in response.json()["detail"]


async def test_foreign_site_not_accessible_via_get(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Site created by another user should return 404."""
    await seed_stand_user(container)

    # Get session to create a foreign user and site
    async with container() as rc:
        session = await rc.get(AsyncSession)
        from app.domains.site.models import Site
        from app.domains.user.models import User

        foreign_user = User(id=uuid.uuid4(), full_name="Foreign User")
        await session.merge(foreign_user)

        foreign_site = Site(
            id=uuid.uuid4(),
            name="Foreign Site",
            address="Foreign Address",
            owner_id=foreign_user.id,
        )
        await session.merge(foreign_site)
        await session.commit()

        foreign_site_id = foreign_site.id

    response = await client.get(f"/sites/{foreign_site_id}")

    assert response.status_code == 404
    assert "Стройка не найдена" in response.json()["detail"]


async def test_foreign_site_not_patchable(client: AsyncClient, container: AsyncContainer) -> None:
    """PATCH on another user's site should return 404."""
    await seed_stand_user(container)

    async with container() as rc:
        session = await rc.get(AsyncSession)
        from app.domains.site.models import Site
        from app.domains.user.models import User

        foreign_user = User(id=uuid.uuid4(), full_name="Foreign User")
        await session.merge(foreign_user)

        foreign_site = Site(
            id=uuid.uuid4(),
            name="Foreign Site",
            owner_id=foreign_user.id,
        )
        await session.merge(foreign_site)
        await session.commit()

        foreign_site_id = foreign_site.id

    response = await client.patch(f"/sites/{foreign_site_id}", json={"name": "Hacked"})

    assert response.status_code == 404
    assert "Стройка не найдена" in response.json()["detail"]


async def test_foreign_site_not_deletable(client: AsyncClient, container: AsyncContainer) -> None:
    """DELETE on another user's site should return 404."""
    await seed_stand_user(container)

    async with container() as rc:
        session = await rc.get(AsyncSession)
        from app.domains.site.models import Site
        from app.domains.user.models import User

        foreign_user = User(id=uuid.uuid4(), full_name="Foreign User")
        await session.merge(foreign_user)

        foreign_site = Site(
            id=uuid.uuid4(),
            name="Foreign Site",
            owner_id=foreign_user.id,
        )
        await session.merge(foreign_site)
        await session.commit()

        foreign_site_id = foreign_site.id

    response = await client.delete(f"/sites/{foreign_site_id}")

    assert response.status_code == 404
    assert "Стройка не найдена" in response.json()["detail"]


async def test_foreign_site_persists_after_delete_attempt(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """After DELETE attempt on foreign site, it should still be in DB."""
    await seed_stand_user(container)

    async with container() as rc:
        session = await rc.get(AsyncSession)
        from app.domains.site.models import Site
        from app.domains.user.models import User

        foreign_user = User(id=uuid.uuid4(), full_name="Foreign User")
        await session.merge(foreign_user)

        foreign_site = Site(
            id=uuid.uuid4(),
            name="Foreign Site",
            owner_id=foreign_user.id,
        )
        await session.merge(foreign_site)
        await session.commit()

        foreign_site_id = foreign_site.id

    # Try to delete
    await client.delete(f"/sites/{foreign_site_id}")

    # Check it's still in DB via direct access
    async with container() as rc:
        session = await rc.get(AsyncSession)
        from sqlalchemy import select

        from app.domains.site.models import Site

        result = await session.execute(select(Site).where(Site.id == foreign_site_id))
        site = result.scalar_one_or_none()
        assert site is not None
        assert site.name == "Foreign Site"


async def test_foreign_site_not_in_list(client: AsyncClient, container: AsyncContainer) -> None:
    """GET /sites should not include sites from other users."""
    await seed_stand_user(container)

    # Create own site
    own_resp = await client.post("/sites", json={"name": "Own Site"})
    own_id = own_resp.json()["id"]

    # Create foreign site
    async with container() as rc:
        session = await rc.get(AsyncSession)
        from app.domains.site.models import Site
        from app.domains.user.models import User

        foreign_user = User(id=uuid.uuid4(), full_name="Foreign User")
        await session.merge(foreign_user)

        foreign_site = Site(
            id=uuid.uuid4(),
            name="Foreign Site",
            owner_id=foreign_user.id,
        )
        await session.merge(foreign_site)
        await session.commit()

    # Get list
    list_resp = await client.get("/sites")

    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) == 1
    assert data[0]["id"] == own_id
    assert data[0]["name"] == "Own Site"


async def test_invalid_uuid_in_path_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed_stand_user(container)

    response = await client.get("/sites/invalid-uuid")

    assert response.status_code == 422
