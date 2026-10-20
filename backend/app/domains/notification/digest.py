"""Сводка по объектам пользователя: текст для руководителя и её рассылка.

Источник уведомлений: собирает из уже посчитанных данных (итог объекта, отклонения,
статусы этапов) один текст и отдаёт его в `NotificationService.notify()`. Каналы и
доставка готовы в домене; здесь только сбор данных, текст и расписание.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from dishka import AsyncContainer

from app.core.settings import DigestSettings, Settings
from app.domains.assessment.models import (
    Decision,
    Severity,
    StageStatusValue,
    deviation_key,
)
from app.domains.assessment.repository import (
    DeviationRepository,
    HypothesisDecisionRepository,
    SiteSummaryRepository,
    StageStatusRepository,
)
from app.domains.notification.models import Notification, NotificationType
from app.domains.notification.service import NotificationService
from app.domains.schedule.repository import ScheduleRepository
from app.domains.site.repository import SiteRepository
from app.plugins.exceptions import AppError

logger = logging.getLogger(__name__)

DIGEST_LINK = "/sites"
# Сколько отстающих этапов называть в строке объекта; остальные — «и ещё N»
MAX_STAGES_PER_SITE = 3
# Телеграм режет сообщение на 4096 знаках, часть уходит на заголовок и ссылку
MAX_BODY_CHARS = 3500


@dataclass(frozen=True)
class StageLag:
    """Отстающий этап: название и сдвиг интервалом (граница None — неизвестна)."""

    name: str
    delay_min: int | None
    delay_max: int | None


@dataclass(frozen=True)
class SiteDigest:
    """Что нужно знать о состоянии одного объекта."""

    name: str
    verdict: str  # "behind" | "no_deviations" | "insufficient_data"
    delay_min: int | None
    delay_max: int | None
    critical: int
    attention: int
    lagging: list[StageLag] = field(default_factory=list)


def format_delay(low: int | None, high: int | None) -> str | None:
    """Сдвиг интервалом: «от 4 дн.», «4–6 дн.», «до 6 дн.»; те же формы, что на фронте."""
    if low is None:
        return None if high is None else f"до {high} дн."
    if high is None:
        return f"от {low} дн."
    if high == low:
        return f"{low} дн."
    return f"{low}–{high} дн."


def _site_status(site: SiteDigest) -> str:
    if site.verdict == "behind":
        delay = format_delay(site.delay_min, site.delay_max)
        return f"отставание {delay}" if delay else "отстаёт от графика"
    if site.verdict == "no_deviations":
        return "в графике"
    return "данных недостаточно"


def _site_block(index: int, site: SiteDigest) -> str:
    lines = [
        f"{index}. {site.name}: {_site_status(site)}",
        f"   Критичных отклонений: {site.critical}, предупреждений: {site.attention}",
    ]
    if site.lagging:
        shown = [
            f"{stage.name} ({delay})"
            if (delay := format_delay(stage.delay_min, stage.delay_max))
            else stage.name
            for stage in site.lagging[:MAX_STAGES_PER_SITE]
        ]
        rest = len(site.lagging) - len(shown)
        tail = f" и ещё {rest}" if rest > 0 else ""
        lines.append(f"   Риски, отстающие этапы: {', '.join(shown)}{tail}")
    return "\n".join(lines)


def render_digest(sites: list[SiteDigest], today: date) -> tuple[str, str]:
    """Заголовок и текст сводки по объектам."""
    critical = sum(site.critical for site in sites)
    attention = sum(site.attention for site in sites)
    title = f"Сводка по объектам на {today:%d.%m.%Y}"
    head = f"Объектов: {len(sites)}. Критичных отклонений: {critical}, предупреждений: {attention}."
    blocks = [_site_block(i, site) for i, site in enumerate(sites, start=1)]
    body = "\n\n".join([head, *blocks])
    if len(body) > MAX_BODY_CHARS:
        body = body[: MAX_BODY_CHARS - 1].rstrip() + "…"
    return title, body


class DigestService:
    """Собирает сводку по объектам пользователя и кладёт её в ленту и каналы."""

    def __init__(
        self,
        sites: SiteRepository,
        summaries: SiteSummaryRepository,
        deviations: DeviationRepository,
        decisions: HypothesisDecisionRepository,
        statuses: StageStatusRepository,
        schedules: ScheduleRepository,
        notifications: NotificationService,
    ) -> None:
        self._sites = sites
        self._summaries = summaries
        self._deviations = deviations
        self._decisions = decisions
        self._statuses = statuses
        self._schedules = schedules
        self._notifications = notifications

    async def collect(self, user_id: uuid.UUID) -> list[SiteDigest]:
        """Состояние каждого объекта пользователя по последнему пересчёту."""
        result: list[SiteDigest] = []
        for site in await self._sites.list_by_owner(user_id):
            result.append(await self._collect_site(site.id, site.name))
        return result

    async def _collect_site(self, site_id: uuid.UUID, name: str) -> SiteDigest:
        decisions = await self._decisions.by_site(site_id)
        critical = attention = 0
        for deviation in await self._deviations.list_by_site(site_id):
            if deviation.is_hypothesis:
                key = deviation_key(deviation.type, deviation.stage_id, deviation.equipment_type_id)
                decided = decisions.get(key)
                # Отклонённая инженером гипотеза в архиве и в счёт не идёт
                if decided is not None and decided.decision == Decision.REJECTED.value:
                    continue
            if deviation.severity == Severity.CRITICAL.value:
                critical += 1
            elif deviation.severity == Severity.ATTENTION.value:
                attention += 1

        summary = await self._summaries.get(site_id)

        lagging: list[StageLag] = []
        schedule = await self._schedules.get_by_site(site_id)
        if schedule is not None:
            stage_names = {s.id: s.name for s in await self._schedules.list_stages(schedule.id)}
            behind = (StageStatusValue.BEHIND.value, StageStatusValue.NOT_STARTED.value)
            for status in await self._statuses.list_by_site(site_id):
                if status.status in behind and status.delay_days is not None:
                    lagging.append(
                        StageLag(
                            name=stage_names.get(status.stage_id, "Этап"),
                            delay_min=status.delay_min,
                            delay_max=status.delay_max,
                        )
                    )

        return SiteDigest(
            name=name,
            verdict=summary.verdict if summary else "insufficient_data",
            delay_min=summary.delay_days_min if summary else None,
            delay_max=summary.delay_days_max if summary else None,
            critical=critical,
            attention=attention,
            lagging=lagging,
        )

    async def send_to(self, user_id: uuid.UUID, today: date | None = None) -> Notification | None:
        """Отправить сводку пользователю; None — объектов нет, слать нечего."""
        sites = await self.collect(user_id)
        if not sites:
            return None
        title, body = render_digest(sites, today or datetime.now(UTC).date())
        return await self._notifications.notify(
            user_id, NotificationType.DIGEST, title, body, link=DIGEST_LINK
        )

    async def send_to_me(self, user_id: uuid.UUID) -> Notification:
        """Ручной запуск из интерфейса: без объектов сводка бессмысленна."""
        created = await self.send_to(user_id)
        if created is None:
            raise AppError("Нет объектов для сводки", status_code=409)
        return created

    async def owners(self) -> list[uuid.UUID]:
        return list(await self._sites.list_owner_ids())


def next_run_after(now: datetime, settings: DigestSettings) -> datetime:
    """Ближайший запуск строго после `now`: заданный день недели и час (UTC)."""
    candidate = now.astimezone(UTC).replace(
        hour=settings.hour_utc, minute=0, second=0, microsecond=0
    )
    candidate += timedelta(days=(settings.weekday - candidate.weekday()) % 7)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


class DigestScheduler:
    """Фоновая задача: раз в неделю рассылает сводку всем владельцам объектов.

    Устроено как TelegramLinkPoller: start()/stop(), запуск в lifespan. Время
    следующего запуска считается от текущего момента, поэтому перезапуск
    приложения не рассылает пропущенную сводку задним числом и не дублирует свежую.
    """

    def __init__(self, container: AsyncContainer, settings: Settings) -> None:
        self._container = container
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def run_once(self) -> int:
        """Разослать сводки всем владельцам; сколько отправлено."""
        async with self._container() as request:
            owners = await (await request.get(DigestService)).owners()
        sent = 0
        for owner_id in owners:
            try:
                # Своя область запроса на пользователя: сбой одного не рушит остальных
                async with self._container() as request:
                    created = await (await request.get(DigestService)).send_to(owner_id)
                sent += created is not None
            except Exception:
                logger.exception("сводка: сбой отправки пользователю %s", owner_id)
        return sent

    async def _loop(self) -> None:
        digest = self._settings.notify.digest
        while not self._stopping.is_set():
            wait = (next_run_after(datetime.now(UTC), digest) - datetime.now(UTC)).total_seconds()
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=max(wait, 1.0))
                return
            except TimeoutError:
                pass
            try:
                sent = await self.run_once()
                logger.info("сводка: отправлено %s", sent)
            except Exception:
                logger.exception("сводка: сбой еженедельной рассылки")

    async def start(self) -> None:
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop(), name="digest-scheduler")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            await self._task
            self._task = None


async def start_digest_scheduler(
    container: AsyncContainer, settings: Settings
) -> DigestScheduler | None:
    """Запустить расписание, если оно включено."""
    if not settings.notify.digest.enabled:
        return None
    scheduler = DigestScheduler(container, settings)
    await scheduler.start()
    return scheduler
