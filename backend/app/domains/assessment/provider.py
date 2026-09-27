"""DI-провайдер домена assessment."""

from dishka import Provider, Scope, provide

from app.core.settings import Settings
from app.domains.assessment.coordinator import AsOfConfig, Clock, RecomputeCoordinator
from app.domains.assessment.engine import EngineConfig, RuleEngine
from app.domains.assessment.recalculator import LiveStatusRecalculator
from app.domains.assessment.repository import (
    DeviationEvidenceRepository,
    DeviationRepository,
    StageStatusRepository,
    StatusBasisRepository,
)
from app.domains.assessment.service import AssessmentService
from app.domains.methodology.recalculator import StatusRecalculator


class AssessmentProvider(Provider):
    """DI-провайдер домена assessment."""

    @provide(scope=Scope.APP)
    def engine_config(self, settings: Settings) -> EngineConfig:
        return EngineConfig(
            tolerance_days=settings.assessment.tolerance_days,
            stale_data_days=settings.assessment.stale_data_days,
            no_progress_window_days=settings.assessment.no_progress_window_days,
            min_confirming_observations=settings.assessment.min_confirming_observations,
        )

    @provide(scope=Scope.APP)
    def engine(self, config: EngineConfig) -> RuleEngine:
        return RuleEngine(config)

    @provide(scope=Scope.APP)
    def clock(self) -> Clock:
        """Провайдер текущей даты для RecomputeCoordinator.

        Возвращает callable, который получает текущую дату.
        Используется Dishka для разрешения зависимости Clock в constructor'е.
        """
        from datetime import date

        return date.today  # type: ignore[return-value]

    @provide(scope=Scope.APP)
    def as_of_config(self, settings: Settings) -> AsOfConfig | None:
        """Режим опорной даты расчёта (LCT-14) — из настроек.

        Тип возврата — AsOfConfig | None, а не просто AsOfConfig: Dishka
        разрешает зависимости конструктора по точной аннотации типа, а
        RecomputeCoordinator.__init__ принимает as_of_config именно как
        AsOfConfig | None (см. Step 2) — без этого auto-wiring падает с
        GraphMissingFactoryError. Сам провайдер всегда возвращает
        конкретный AsOfConfig, никогда None.
        """
        return AsOfConfig(
            mode=settings.assessment.as_of_mode,
            fixed_date=settings.assessment.as_of_override,
        )

    stage_status_repository = provide(StageStatusRepository, scope=Scope.REQUEST)
    deviation_repository = provide(DeviationRepository, scope=Scope.REQUEST)
    deviation_evidence_repository = provide(DeviationEvidenceRepository, scope=Scope.REQUEST)
    status_basis_repository = provide(StatusBasisRepository, scope=Scope.REQUEST)
    coordinator = provide(RecomputeCoordinator, scope=Scope.REQUEST)
    service = provide(AssessmentService, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST, provides=StatusRecalculator)
    def status_recalculator(self, coordinator: RecomputeCoordinator) -> StatusRecalculator:
        """Перекрывает NoopStatusRecalculator из MethodologyProvider (регистрация после него)."""
        return LiveStatusRecalculator(coordinator)
