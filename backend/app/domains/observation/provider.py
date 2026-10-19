"""DI-провайдер домена observation."""

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.methodology.recalculator import (
    NoopStatusRecalculator,
    StatusRecalculator,
)
from app.domains.observation.activity import ActivityParams
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
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.site.guard import SiteAccessGuard


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
        cfg = settings.observation
        return ActivityPolicy(
            ActivityParams(
                still_shift=cfg.still_shift,
                moved_shift=cfg.moved_shift,
                max_gap_min=cfg.pair_max_gap_min,
                idle_min_pairs=cfg.idle_min_pairs,
            )
        )

    @provide(scope=Scope.APP, provides=StatusRecalculator)
    def status_recalculator(self) -> StatusRecalculator:
        """Предоставить no-op рекалькулятор (заглушка для LCT-11)."""
        return NoopStatusRecalculator()

    observation_repository = provide(ObservationRepository, scope=Scope.REQUEST)
    observed_equipment_repository = provide(ObservedEquipmentRepository, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def service(
        self,
        repository: ObservationRepository,
        equipment_repo: ObservedEquipmentRepository,
        photos: PhotoRepository,
        detections: DetectionRepository,
        session: AsyncSession,
        guard: SiteAccessGuard,
        catalog: EquipmentCatalog,
        aggregation: AggregationPolicy,
        observability: ObservabilityPolicy,
        activity: ActivityPolicy,
        recalculator: StatusRecalculator,
    ) -> ObservationService:
        """Сервис для HTTP-роутов: с гвардом доступа к стройке."""
        return ObservationService(
            repository=repository,
            equipment_repo=equipment_repo,
            photos=photos,
            detections=detections,
            session=session,
            guard=guard,
            catalog=catalog,
            aggregation=aggregation,
            observability=observability,
            activity=activity,
            recalculator=recalculator,
        )

    @provide(scope=Scope.REQUEST, provides=ObservationRecalculator)
    def observation_recalculator(
        self,
        repository: ObservationRepository,
        equipment_repo: ObservedEquipmentRepository,
        photos: PhotoRepository,
        detections: DetectionRepository,
        session: AsyncSession,
        catalog: EquipmentCatalog,
        aggregation: AggregationPolicy,
        observability: ObservabilityPolicy,
        activity: ActivityPolicy,
        recalculator: StatusRecalculator,
    ) -> ObservationRecalculator:
        """Перекрывает NoopObservationRecalculator из PhotoProvider (регистрация после него).

        Пересчёт — системное действие после загрузки, кадра со стрима или очереди обработки:
        доступ к стройке уже проверил вызывающий. Поэтому сервис собирается без гварда — гвард
        требует текущего пользователя, а его нет вне HTTP-запроса (фоновые задачи падали
        с NoContextValueError).
        """
        return LiveObservationRecalculator(
            ObservationService(
                repository=repository,
                equipment_repo=equipment_repo,
                photos=photos,
                detections=detections,
                session=session,
                guard=None,
                catalog=catalog,
                aggregation=aggregation,
                observability=observability,
                activity=activity,
                recalculator=recalculator,
            )
        )
