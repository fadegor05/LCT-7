"""HTTP-роуты объектов строительства."""

import uuid

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Response

from app.domains.site.schemas import SiteCreate, SiteRead, SiteUpdate
from app.domains.site.service import SiteService

router = APIRouter(prefix="/sites", tags=["sites"])


@router.post("", status_code=201)
@inject
async def create_site(data: SiteCreate, service: FromDishka[SiteService]) -> SiteRead:
    site = await service.create(data)
    return SiteRead.model_validate(site)


@router.get("")
@inject
async def list_sites(service: FromDishka[SiteService]) -> list[SiteRead]:
    sites = await service.list()
    return [SiteRead.model_validate(site) for site in sites]


@router.get("/{site_id}")
@inject
async def get_site(site_id: uuid.UUID, service: FromDishka[SiteService]) -> SiteRead:
    site = await service.get(site_id)
    return SiteRead.model_validate(site)


@router.patch("/{site_id}")
@inject
async def update_site(
    site_id: uuid.UUID, data: SiteUpdate, service: FromDishka[SiteService]
) -> SiteRead:
    site = await service.update(site_id, data)
    return SiteRead.model_validate(site)


@router.delete("/{site_id}", status_code=204)
@inject
async def delete_site(site_id: uuid.UUID, service: FromDishka[SiteService]) -> Response:
    await service.delete(site_id)
    return Response(status_code=204)
