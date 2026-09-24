"""DI-провайдер домена observation."""

from dishka import Provider, Scope, provide

from app.core.settings import Settings
from app.domains.observation.policies import (
    ActivityPolicy,
    AggregationPolicy,
    ObservabilityPolicy,
)
from app.domains.observation.recalculator import LiveObservationRecalculator
from app.domains.observation.repository import (
    ObservationRepository,
    ObservedEquipmentRepository,
)
from app.domains.observation.service import ObservationService
from app.domains.photo.recalculator import ObservationRecalculator


class ObservationProvider(Provider):
    """DI-провайдер домена observation."""

    @provide(scope=Scope.APP)
    def aggregation_policy(self, settings: Settings) -> AggregationPolicy:
        """Создать AggregationPolicy."""
        return AggregationPolicy(
            min_score_high=settings.observation.min_score_high,
            min_score_medium=settings.observation.min_score_medium,
        )

    @provide(scope=Scope.APP)
    def observability_policy(self, settings: Settings) -> ObservabilityPolicy:
        """Создать ObservabilityPolicy."""
        return ObservabilityPolicy(
            min_photos_medium=settings.observation.min_photos_medium,
            min_photos_high=settings.observation.min_photos_high,
        )

    @provide(scope=Scope.APP)
    def activity_policy(self, settings: Settings) -> ActivityPolicy:
        """Создать ActivityPolicy."""
        return ActivityPolicy(movement_threshold=settings.observation.movement_threshold)

    observation_repository = provide(ObservationRepository, scope=Scope.REQUEST)
    observed_equipment_repository = provide(ObservedEquipmentRepository, scope=Scope.REQUEST)
    service = provide(ObservationService, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST, provides=ObservationRecalculator)
    def observation_recalculator(self, service: ObservationService) -> ObservationRecalculator:
        """Перекрывает NoopObservationRecalculator из PhotoProvider (регистрация после него)."""
        return LiveObservationRecalculator(service)
