"""DI-провайдер домена camera."""

from dishka import Provider, Scope, provide

from app.domains.camera.repository import CameraRepository
from app.domains.camera.service import CameraService


class CameraProvider(Provider):
    scope = Scope.REQUEST

    repository = provide(CameraRepository)
    service = provide(CameraService)
