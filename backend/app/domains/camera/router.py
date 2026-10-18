"""HTTP-роуты камер стройки."""

import uuid

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Response

from app.domains.camera.capture import CameraCaptureService
from app.domains.camera.schemas import CameraIn, CameraRead, CameraUpdate
from app.domains.camera.service import CameraService, CameraView
from app.domains.photo.schemas import PhotoRead

router = APIRouter(prefix="/sites/{site_id}/cameras", tags=["cameras"])


def _read(view: CameraView) -> CameraRead:
    c = view.camera
    return CameraRead(
        id=c.id,
        name=c.name,
        stream_url=c.stream_url,
        capture_every_s=c.capture_every_s,
        last_capture_at=c.last_capture_at,
        last_capture_error=c.last_capture_error,
        zone=c.zone,
        frames_count=view.frames_count,
        created_at=c.created_at,
    )


@router.get("")
@inject
async def list_cameras(site_id: uuid.UUID, service: FromDishka[CameraService]) -> list[CameraRead]:
    return [_read(view) for view in await service.for_site(site_id)]


@router.post("", status_code=201)
@inject
async def create_camera(
    site_id: uuid.UUID, data: CameraIn, service: FromDishka[CameraService]
) -> CameraRead:
    return _read(await service.create(site_id, data))


@router.patch("/{camera_id}")
@inject
async def update_camera(
    site_id: uuid.UUID,
    camera_id: uuid.UUID,
    data: CameraUpdate,
    service: FromDishka[CameraService],
) -> CameraRead:
    return _read(await service.update(site_id, camera_id, data))


@router.post("/{camera_id}/capture", status_code=201)
@inject
async def capture_camera(
    site_id: uuid.UUID, camera_id: uuid.UUID, service: FromDishka[CameraCaptureService]
) -> PhotoRead:
    """«Снять кадр сейчас» со стрима камеры: кадр сразу в ленту, либо 422 с причиной."""
    return await service.capture_now(site_id, camera_id)


@router.delete("/{camera_id}", status_code=204)
@inject
async def delete_camera(
    site_id: uuid.UUID, camera_id: uuid.UUID, service: FromDishka[CameraService]
) -> Response:
    await service.delete(site_id, camera_id)
    return Response(status_code=204)
