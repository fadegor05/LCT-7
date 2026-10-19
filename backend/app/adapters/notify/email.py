"""Почта: SMTP-клиент и канал доставки поверх него.

Единственное место в проекте, знающее про SMTP. Пароль в логи не пишется.
"""

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from typing import ClassVar

from app.adapters.notify.base import ChannelMessage, NotifyError
from app.core.settings import EmailSettings
from app.domains.notification.models import ChannelKind


def build_message(from_addr: str, to_addr: str, message: ChannelMessage) -> EmailMessage:
    """Собрать письмо: заголовок в теме, текст и ссылка в теле. Только text/plain."""
    mail = EmailMessage()
    mail["From"] = from_addr
    mail["To"] = to_addr
    mail["Subject"] = message.title
    parts = [message.body]
    if message.link:
        parts += ["", message.link]
    mail.set_content("\n".join(parts))
    return mail


class SmtpClient:
    """Обёртка над smtplib. smtplib блокирующий, поэтому уходит в поток."""

    def __init__(self, settings: EmailSettings) -> None:
        self._settings = settings

    def _redact(self, text: str) -> str:
        password = self._settings.password
        return text.replace(password, "***") if password else text

    def _send_sync(self, mail: EmailMessage) -> None:
        cfg = self._settings
        if cfg.host is None:
            raise NotifyError("SMTP не настроен")
        if cfg.use_ssl:
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(
                cfg.host, cfg.port, timeout=cfg.timeout_s, context=ssl.create_default_context()
            )
        else:
            smtp = smtplib.SMTP(cfg.host, cfg.port, timeout=cfg.timeout_s)
        with smtp:
            if cfg.starttls and not cfg.use_ssl:
                smtp.starttls(context=ssl.create_default_context())
            if cfg.username and cfg.password:
                smtp.login(cfg.username, cfg.password)
            smtp.send_message(mail)

    async def send(self, mail: EmailMessage) -> None:
        try:
            await asyncio.to_thread(self._send_sync, mail)
        except NotifyError:
            raise
        except Exception as error:
            detail = self._redact(str(error)).strip()
            name = type(error).__name__
            raise NotifyError(f"SMTP: {name}: {detail}" if detail else f"SMTP: {name}") from error


class EmailChannel:
    """Доставка уведомления на почту."""

    kind: ClassVar[ChannelKind] = ChannelKind.EMAIL

    def __init__(self, client: SmtpClient, from_addr: str) -> None:
        self._client = client
        self._from_addr = from_addr

    async def send(self, address: str, message: ChannelMessage) -> None:
        await self._client.send(build_message(self._from_addr, address, message))
