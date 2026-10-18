"""Обёртка над снимателем: служебные и частные адреса, одна съёмка на камеру, общий лимит.

Регистрация открыта, а снимает сервер: без проверки любой пользователь мог бы указать
«камерой» адрес самого сервиса (`http://minio:9000/…`, `127.0.0.1`, метаданные облака) и
изучать внутреннюю сеть по ответам. Закрыты всегда: петля, link-local, «любой адрес»,
мультикаст, зарезервированные адреса, службы compose (`STREAM__BLOCKED_HOSTS`) и сети из
`STREAM__BLOCKED_NETWORKS`. Частные сети (камеры на стройке живут в них) закрыты, пока их
не разрешит `STREAM__ALLOWED_NETWORKS`; разрешение не открывает закрытое выше.

Адреса проверяются после DNS-разрешения, а не по тексту ссылки. Редиректы HTTP и смена
ответа DNS между проверкой и ffmpeg этим не закрываются (см. отчёт о стриме).
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from app.adapters.stream.base import StreamBusy, StreamError, StreamGrabber
from app.core.settings import Settings

SERVICE_ADDRESS = "Это адрес самого сервиса, а не камеры"
PRIVATE_ADDRESS = "Адрес в частной сети не разрешён настройками сервиса (STREAM__ALLOWED_NETWORKS)"
Resolver = Callable[[str], Awaitable[list[str]]]
IP = ipaddress.IPv4Address | ipaddress.IPv6Address


async def resolve_host(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        return []  # не резолвится — скажет ffmpeg
    return [str(info[4][0]) for info in infos]


def _parse(address: str) -> IP | None:
    try:
        ip: IP = ipaddress.ip_address(address.split("%")[0])
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return ip.ipv4_mapped
    return ip


def _always_closed(ip: IP) -> bool:
    return (
        ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast or ip.is_reserved
    )


class GuardedGrabber:
    def __init__(
        self, inner: StreamGrabber, settings: Settings, resolve: Resolver = resolve_host
    ) -> None:
        cfg = settings.stream
        self._inner = inner
        self._resolve = resolve
        self._blocked = [ipaddress.ip_network(n, strict=False) for n in cfg.blocked_networks]
        self._allowed = [ipaddress.ip_network(n, strict=False) for n in cfg.allowed_networks]
        self._service_hosts = {h.lower() for h in cfg.blocked_hosts}
        # Общий на снимки по расписанию и «Снять кадр сейчас»: ffmpeg-процессов не больше K
        self._limit = asyncio.Semaphore(cfg.concurrency)
        self._busy: set[str] = set()

    async def _check(self, url: str) -> None:
        host = (urlsplit(url).hostname or "").lower()
        if not host:
            raise StreamError("В ссылке нет адреса камеры")
        if host in self._service_hosts:
            raise StreamError(SERVICE_ADDRESS)
        service_ips: set[str] = set()
        for name in self._service_hosts:
            service_ips.update(await self._resolve(name))
        for address in await self._resolve(host):
            ip = _parse(address)
            if ip is None:
                continue
            if address in service_ips or _always_closed(ip):
                raise StreamError(SERVICE_ADDRESS)
            if any(ip in net for net in self._blocked):
                raise StreamError(SERVICE_ADDRESS)
            if ip.is_private and not any(ip in net for net in self._allowed):
                raise StreamError(PRIVATE_ADDRESS)

    async def grab(self, url: str) -> bytes:
        await self._check(url)
        if url in self._busy:
            raise StreamBusy("Снимок с этой камеры уже идёт")
        self._busy.add(url)
        try:
            async with self._limit:
                return await self._inner.grab(url)
        finally:
            self._busy.discard(url)
