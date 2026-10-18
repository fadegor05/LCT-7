"""DI-провайдеры домена camera и снимков со стрима."""

from dishka import Provider, Scope, provide

from app.adapters.stream.base import StreamGrabber
from app.adapters.stream.ffmpeg import FfmpegGrabber
from app.adapters.stream.guard import GuardedGrabber
from app.core.settings import Settings
from app.domains.camera.capture import CameraCaptureService, CameraFrameIngest
from app.domains.camera.repository import CameraRepository
from app.domains.camera.service import CameraService
from app.domains.camera.stream import StreamCapture


class CameraProvider(Provider):
    scope = Scope.REQUEST

    repository = provide(CameraRepository)
    service = provide(CameraService)
    capture = provide(CameraCaptureService)
    frames = provide(CameraFrameIngest)


class StreamGrabberProvider(Provider):
    """Сниматель стрима: ffmpeg за защитой адресов. Один на приложение."""

    scope = Scope.APP

    @provide
    def grabber(self, settings: Settings) -> StreamGrabber:
        return GuardedGrabber(FfmpegGrabber(timeout_s=settings.stream.timeout_s), settings)


class StreamCaptureProvider(Provider):
    """Фоновый планировщик: создаётся, только если STREAM__ENABLED=true (см. main.py)."""

    scope = Scope.APP

    capture = provide(StreamCapture)
