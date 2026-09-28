"""DI-провайдер домена assistant."""

from dishka import Provider, Scope, provide

from app.domains.assistant.service import AssistantReportService


class AssistantProvider(Provider):
    """DI-провайдер домена assistant."""

    service = provide(AssistantReportService, scope=Scope.REQUEST)
