"""DI-провайдер домена schedule."""

from dishka import Provider, Scope, provide

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
