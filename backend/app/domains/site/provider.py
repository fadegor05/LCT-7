"""DI-провайдер домена site."""

from dishka import Provider, Scope, provide

from app.domains.site.guard import SiteAccessGuard
from app.domains.site.repository import SiteRepository
from app.domains.site.service import SiteService


class SiteProvider(Provider):
    scope = Scope.REQUEST

    repository = provide(SiteRepository)
    guard = provide(SiteAccessGuard)
    service = provide(SiteService)
