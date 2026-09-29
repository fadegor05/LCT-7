"""DI контейнер для observation домена: ObservationProvider и wire-up."""

import pytest

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
from app.domains.photo.provider import PhotoProvider
from app.domains.photo.recalculator import NoopObservationRecalculator, ObservationRecalculator
from app.plugins.di import create_container


class TestObservationProviderWiring:
    """Тесты wire-up ObservationProvider в основной DI контейнер."""

    @pytest.mark.asyncio
    async def test_create_container_resolves_aggregation_policy(self) -> None:
        """create_container() может разрешить AggregationPolicy в APP scope."""
        container = create_container()
        try:
            policy = await container.get(AggregationPolicy)
            assert isinstance(policy, AggregationPolicy)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_create_container_resolves_observability_policy(self) -> None:
        """create_container() может разрешить ObservabilityPolicy в APP scope."""
        container = create_container()
        try:
            policy = await container.get(ObservabilityPolicy)
            assert isinstance(policy, ObservabilityPolicy)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_create_container_resolves_activity_policy(self) -> None:
        """create_container() может разрешить ActivityPolicy в APP scope."""
        container = create_container()
        try:
            policy = await container.get(ActivityPolicy)
            assert isinstance(policy, ActivityPolicy)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_create_container_resolves_observation_repository(self) -> None:
        """create_container() может разрешить ObservationRepository в REQUEST scope."""
        container = create_container()
        try:
            async with container() as request_container:
                repo = await request_container.get(ObservationRepository)
                assert isinstance(repo, ObservationRepository)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_create_container_resolves_observed_equipment_repository(self) -> None:
        """create_container() может разрешить ObservedEquipmentRepository в REQUEST scope."""
        container = create_container()
        try:
            async with container() as request_container:
                repo = await request_container.get(ObservedEquipmentRepository)
                assert isinstance(repo, ObservedEquipmentRepository)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_create_container_resolves_observation_service(self, container) -> None:
        """Test container может разрешить ObservationService в REQUEST scope."""
        # Need to seed stand user first since ObservationService depends on SiteAccessGuard
        async with container() as request_container:
            from app.domains.user.service import UserService

            user_service = await request_container.get(UserService)
            await user_service.ensure_stand_user()

        # Now resolve ObservationService
        async with container() as request_container:
            service = await request_container.get(ObservationService)
            assert isinstance(service, ObservationService)

    @pytest.mark.asyncio
    async def test_app_scope_policies_are_reused(self, container) -> None:
        """APP scope политики переиспользуются между REQUEST контекстами."""
        async with container() as request_container1:
            policy1 = await request_container1.get(AggregationPolicy)

        async with container() as request_container2:
            policy2 = await request_container2.get(AggregationPolicy)

        # Они должны быть одинаковыми объектами (переиспользованы)
        assert policy1 is policy2

    @pytest.mark.asyncio
    async def test_request_scope_repositories_are_different(self, container) -> None:
        """REQUEST scope репозитории создаются новые в каждом REQUEST контексте."""
        async with container() as request_container1:
            repo1 = await request_container1.get(ObservationRepository)

        async with container() as request_container2:
            repo2 = await request_container2.get(ObservationRepository)

        # Они должны быть разными объектами (новые для каждого контекста)
        assert repo1 is not repo2

    @pytest.mark.asyncio
    async def test_create_container_resolves_live_recalculator(self, container) -> None:
        """Test container resolve LiveObservationRecalculator (не Noop).

        Это критический тест (Review Focus #5): проверяет, что ObservationProvider
        зарегистрирован ПОСЛЕ PhotoProvider в conftest.py, поэтому реальная
        реализация (Live) переопределяет no-op заглушку из PhotoProvider.
        Используем test container с in-memory SQLite вместо production container.
        """
        # Need to seed stand user first since LiveObservationRecalculator depends on
        # ObservationService which depends on SiteAccessGuard
        async with container() as request_container:
            from app.domains.user.service import UserService

            user_service = await request_container.get(UserService)
            await user_service.ensure_stand_user()

        # Now resolve ObservationRecalculator
        async with container() as request_container:
            recalculator = await request_container.get(ObservationRecalculator)
            assert isinstance(recalculator, LiveObservationRecalculator)
            # Убедиться, что это точно LIVE, а не Noop
            assert not isinstance(recalculator, NoopObservationRecalculator)

    @pytest.mark.asyncio
    async def test_photo_only_container_resolves_noop_recalculator(self) -> None:
        """Контейнер с только PhotoProvider() (без ObservationProvider) использует Noop.

        Это доказывает, что photo домен деградирует корректно без observation,
        когда observation не подключён в контейнер.
        """
        from dishka import make_async_container

        from app.domains.methodology.provider import MethodologyProvider
        from app.domains.schedule.provider import ScheduleLlmClientProvider, ScheduleProvider
        from app.domains.site.provider import SiteProvider
        from app.domains.user.provider import UserProvider
        from app.domains.utility.provider import UtilityProvider
        from app.plugins.di import AppProvider, DatabaseProvider

        # Строим контейнер БЕЗ ObservationProvider
        container = make_async_container(
            AppProvider(),
            DatabaseProvider(),
            UserProvider(),
            SiteProvider(),
            ScheduleProvider(),
            ScheduleLlmClientProvider(),
            MethodologyProvider(),
            PhotoProvider(),
            # Заметьте: ObservationProvider() НЕ включён здесь
            UtilityProvider(),
        )

        try:
            async with container() as request_container:
                recalculator = await request_container.get(ObservationRecalculator)
                # Должен быть Noop, т.к. ObservationProvider() не подключён
                assert isinstance(recalculator, NoopObservationRecalculator)
                assert not isinstance(recalculator, LiveObservationRecalculator)
        finally:
            await container.close()

    def test_create_container_registers_observation_provider_after_photo_provider(self) -> None:
        """Review Focus #5: production di.py must register ObservationProvider() after
        PhotoProvider() — reversed order silently resurrects the no-op recalculator with
        no other test failure anywhere."""
        import inspect

        from app.plugins import di as di_module

        source = inspect.getsource(di_module.create_container)
        photo_index = source.index("PhotoProvider()")
        observation_index = source.index("ObservationProvider()")
        assert photo_index < observation_index, (
            "PhotoProvider() must be registered before ObservationProvider() in "
            "create_container() so the real LiveObservationRecalculator overrides the no-op"
        )
