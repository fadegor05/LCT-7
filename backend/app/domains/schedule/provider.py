"""DI-провайдер домена schedule."""

from dishka import Provider, Scope, provide

from app.domains.schedule.parser import ScheduleParser
from app.domains.schedule.repository import ScheduleRepository
from app.domains.schedule.service import ScheduleService


class ScheduleProvider(Provider):
    """DI провайдер для домена schedule."""

    # Parser в Scope.APP (stateless, можно переиспользовать)
    parser = provide(ScheduleParser, scope=Scope.APP)

    # Repository и Service в Scope.REQUEST (привязаны к сессии)
    repository = provide(ScheduleRepository, scope=Scope.REQUEST)
    service = provide(ScheduleService, scope=Scope.REQUEST)
