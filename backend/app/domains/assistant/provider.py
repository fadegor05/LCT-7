"""DI-провайдер домена assistant."""

from dishka import Provider, Scope, provide

from app.adapters.ml.assistant import AssistantClient
from app.adapters.ml.factory import create_assistant
from app.adapters.ml.http import DetectorHttpClient
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.settings import Settings
from app.domains.assistant.ask_service import AssistantService
from app.domains.assistant.service import AssistantReportService
from app.domains.site.guard import SiteAccessGuard


class AssistantProvider(Provider):
    """DI-провайдер домена assistant."""

    report_service = provide(AssistantReportService, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def rate_limiter(self, settings: Settings) -> SlidingWindowRateLimiter:
        """Создать rate limiter на основе настроек.

        Использует settings.assistant.rate_limit_per_min, окно 60 секунд.
        """
        return SlidingWindowRateLimiter(
            limit=settings.assistant.rate_limit_per_min,
            window_s=60.0,
        )

    @provide(scope=Scope.REQUEST)
    async def service(
        self,
        reports: AssistantReportService,
        client: AssistantClient,
        limiter: SlidingWindowRateLimiter,
        guard: SiteAccessGuard,
        settings: Settings,
    ) -> AssistantService:
        """Создать AssistantService."""
        return AssistantService(
            reports=reports,
            client=client,
            limiter=limiter,
            guard=guard,
            settings=settings,
        )


class AssistantClientProvider(Provider):
    """DI-провайдер для HTTP клиента ассистента.

    Создаёт HttpAssistantClient или NullAssistantClient в зависимости от настроек.
    Переиспользует shared DetectorHttpClient из PhotoProvider.
    """

    @provide(scope=Scope.APP)
    def assistant_client(
        self,
        settings: Settings,
        http_client: DetectorHttpClient,
    ) -> AssistantClient:
        """Создать AssistantClient (Http или Null).

        Args:
            settings: Глобальные настройки
            http_client: Shared httpx.AsyncClient, обёрнутый в DetectorHttpClient

        Returns:
            HttpAssistantClient если detector.url настроена, иначе NullAssistantClient
        """
        # Unwrap the NewType to get the underlying AsyncClient
        return create_assistant(settings, http_client)  # type: ignore
