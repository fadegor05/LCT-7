"""DI-провайдер домена schedule."""

from dishka import Provider, Scope, provide

from app.adapters.ml.factory import create_schedule_llm
from app.adapters.ml.http import DetectorHttpClient
from app.adapters.ml.schedule_llm import ScheduleLlmClient
from app.core.settings import Settings
from app.domains.methodology.recalculator import (
    NoopStatusRecalculator,
    StatusRecalculator,
)
from app.domains.schedule.parser import ScheduleParser
from app.domains.schedule.repository import ScheduleRepository
from app.domains.schedule.service import ScheduleService


class ScheduleProvider(Provider):
    """DI провайдер для домена schedule."""

    # Parser в Scope.APP (stateless, можно переиспользовать)
    parser = provide(ScheduleParser, scope=Scope.APP)

    @provide(scope=Scope.APP, provides=StatusRecalculator)
    def status_recalculator(self) -> StatusRecalculator:
        """Предоставить no-op рекалькулятор (заглушка для LCT-11)."""
        return NoopStatusRecalculator()

    # Repository и Service в Scope.REQUEST (привязаны к сессии)
    repository = provide(ScheduleRepository, scope=Scope.REQUEST)
    service = provide(ScheduleService, scope=Scope.REQUEST)


class ScheduleLlmClientProvider(Provider):
    """DI-провайдер LLM-разбора плана: Http или Null — по настройкам ML-сервиса.

    Переиспользует общий httpx-клиент ML (DetectorHttpClient из PhotoProvider).
    """

    @provide(scope=Scope.APP)
    def schedule_llm(
        self, settings: Settings, http_client: DetectorHttpClient
    ) -> ScheduleLlmClient:
        return create_schedule_llm(settings, http_client)  # type: ignore[arg-type]
