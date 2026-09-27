"""DI-провайдер домена utility."""

from dishka import Provider, Scope, provide

from app.domains.utility.service import HealthService


class UtilityProvider(Provider):
    scope = Scope.REQUEST

    service = provide(HealthService)
