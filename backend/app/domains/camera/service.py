"""Бизнес-логика камер стройки и их рабочих зон."""

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.camera.models import Camera
from app.domains.camera.repository import CameraRepository
from app.domains.camera.schemas import CameraIn, CameraUpdate
from app.domains.site.guard import SiteAccessGuard
from app.plugins.exceptions import AppError

# Со ссылкой на стрим снимаем по умолчанию раз в 5 минут
DEFAULT_CAPTURE_EVERY_S = 300
# Протоколы, по которым снимается кадр; локальные (`file:`) не принимаем
STREAM_SCHEMES = ("rtsp://", "rtsps://", "http://", "https://")
MAX_STREAM_URL_LENGTH = 500
# Схема и учётные данные (до последнего «@») — как в adapters/stream/base.mask_credentials
_CREDENTIALS = re.compile(r"([a-z][a-z0-9+.-]*://)(\S*)@", re.IGNORECASE)
_MASKED_CREDENTIALS = re.compile(r"([a-z][a-z0-9+.-]*://)\*\*\*@", re.IGNORECASE)


@dataclass
class CameraView:
    """Камера и число фотографий, привязанных к ней."""

    camera: Camera
    frames_count: int


class CameraService:
    def __init__(
        self,
        repository: CameraRepository,
        session: AsyncSession,
        guard: SiteAccessGuard,
    ) -> None:
        self._repository = repository
        self._session = session
        self._guard = guard

    async def for_site(self, site_id: uuid.UUID) -> list[CameraView]:
        await self._guard.require(site_id)
        cameras = await self._repository.for_site(site_id)
        return await self._views(cameras)

    async def create(self, site_id: uuid.UUID, data: CameraIn) -> CameraView:
        await self._guard.require(site_id)
        camera = Camera(
            site_id=site_id,
            name=data.name,
            stream_url=resolve_stream_url(data.stream_url),
            zone=data.zone,
        )
        camera.capture_every_s = _interval(camera.stream_url, data.capture_every_s)
        await self._repository.add(camera)
        await self._session.commit()
        await self._session.refresh(camera)
        return CameraView(camera, 0)

    async def update(
        self, site_id: uuid.UUID, camera_id: uuid.UUID, data: CameraUpdate
    ) -> CameraView:
        camera = await self._get(site_id, camera_id)
        changes = data.model_dump(exclude_unset=True)
        if "stream_url" in changes:
            changes["stream_url"] = resolve_stream_url(
                changes["stream_url"], stored=camera.stream_url
            )
        stream_changed = "stream_url" in changes and changes["stream_url"] != camera.stream_url
        for field, value in changes.items():
            setattr(camera, field, value)
        camera.capture_every_s = _interval(camera.stream_url, camera.capture_every_s)
        if stream_changed:  # новая ссылка — сбои старой не в счёт
            camera.capture_failures = 0
            camera.last_capture_error = None
            camera.last_capture_attempt_at = None
        await self._session.commit()
        await self._session.refresh(camera)
        return (await self._views([camera]))[0]

    async def delete(self, site_id: uuid.UUID, camera_id: uuid.UUID) -> None:
        """Удалить камеру; её фотографии остаются, их camera_id обнуляется (ON DELETE SET NULL)."""
        camera = await self._get(site_id, camera_id)
        await self._repository.delete(camera)
        await self._session.commit()

    async def _get(self, site_id: uuid.UUID, camera_id: uuid.UUID) -> Camera:
        await self._guard.require(site_id)
        camera = await self._repository.get(camera_id)
        if camera is None or camera.site_id != site_id:
            raise AppError("Камера не найдена", status_code=404)
        return camera

    async def _views(self, cameras: Sequence[Camera]) -> list[CameraView]:
        counts = await self._repository.photo_counts([c.id for c in cameras])
        return [CameraView(c, counts.get(c.id, 0)) for c in cameras]


def resolve_stream_url(value: str | None, stored: str | None = None) -> str | None:
    """Проверить ссылку на стрим; пустая — None.

    API отдаёт ссылку с паролем замаскированным (`rtsp://***@host`). Если такую ссылку прислали
    обратно, берём учётные данные из сохранённой, иначе — 422 (пароля в базе нет или ссылка новая).

    Текст ошибки не содержит саму ссылку: в ней могут быть учётные данные камеры.
    """
    if value is None or not value.strip():
        return None
    url = value.strip()
    if len(url) > MAX_STREAM_URL_LENGTH:
        raise AppError(
            f"ссылка на стрим — не длиннее {MAX_STREAM_URL_LENGTH} символов", status_code=422
        )
    if not url.lower().startswith(STREAM_SCHEMES):
        raise AppError("ссылка на стрим — rtsp://, rtsps://, http:// или https://", status_code=422)
    return _with_stored_credentials(url, stored)


def _with_stored_credentials(url: str, stored: str | None) -> str:
    """`rtsp://***@host` → `rtsp://<логин:пароль из сохранённой ссылки>@host`."""
    masked = _MASKED_CREDENTIALS.match(url)
    if masked is None:
        return url
    kept = _CREDENTIALS.match(stored or "")
    if kept is None:
        raise AppError("ссылка на стрим — вставьте её целиком, с паролем", status_code=422)
    return f"{masked.group(1)}{kept.group(2)}@{url[masked.end() :]}"


def _interval(stream_url: str | None, every_s: int | None) -> int | None:
    """Со ссылкой снимаем всегда, без ссылки снимать нечего."""
    if stream_url is None:
        return None
    return every_s or DEFAULT_CAPTURE_EVERY_S
