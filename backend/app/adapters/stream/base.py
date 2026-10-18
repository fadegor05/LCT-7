"""Снимок одного кадра со стрима камеры: протокол и ошибки."""

import re
from typing import Protocol

# До последнего «@» в ссылке: пароль часто вставляют как есть, с «@» или «/» внутри
_CREDENTIALS = re.compile(r"([a-z][a-z0-9+.-]*://)\S*@", re.IGNORECASE)


def mask_credentials(text: str) -> str:
    """`rtsp://admin:secret@host` → `rtsp://***@host`: пароль камеры не идёт в ответы и логи."""
    return _CREDENTIALS.sub(r"\1***@", text)


class StreamError(Exception):
    """Кадр не получен; текст — для инженера, без учётных данных из ссылки."""


class StreamBusy(StreamError):
    """С этой камеры кадр уже снимается: второй снимок параллельно не запускаем."""


class StreamGrabber(Protocol):
    async def grab(self, url: str) -> bytes:
        """Один кадр JPEG со стрима; иначе `StreamError`."""
        ...
