"""DI-провайдер домена methodology."""

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.methodology.defaults import DefaultRuleSet
from app.domains.methodology.materializer import RuleMaterializer
from app.domains.methodology.recalculator import NoopStatusRecalculator, StatusRecalculator
from app.domains.methodology.repository import MethodologyRepository
from app.domains.methodology.service import MethodologyService


class MethodologyProvider(Provider):
    """DI провайдер для домена methodology."""

    # APP-scoped: каталог оборудования, рекалькулятор, правила по умолчанию
    @provide(scope=Scope.APP)
    def equipment_catalog(self, sessionmaker: async_sessionmaker[AsyncSession]) -> EquipmentCatalog:
        """Предоставить кешированный каталог оборудования."""
        return EquipmentCatalog(sessionmaker)

    @provide(scope=Scope.APP, provides=StatusRecalculator)
    def status_recalculator(self) -> StatusRecalculator:
        """Предоставить no-op рекалькулятор (заглушка для LCT-11)."""
        return NoopStatusRecalculator()

    @provide(scope=Scope.APP)
    def default_rule_set(self) -> DefaultRuleSet:
        """Предоставить набор правил по умолчанию (stateless)."""
        return DefaultRuleSet()

    # REQUEST-scoped: репозиторий и сервис
    repository = provide(MethodologyRepository, scope=Scope.REQUEST)
    materializer = provide(RuleMaterializer, scope=Scope.REQUEST)
    service = provide(MethodologyService, scope=Scope.REQUEST)
