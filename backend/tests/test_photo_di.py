"""DI контейнер для photo домена: PhotoProvider и wire-up."""

import pytest

from app.adapters.ml.base import DetectorClient
from app.adapters.ml.null import NullDetector
from app.adapters.storage.base import FileStorage
from app.adapters.storage.local import LocalFileStorage
from app.domains.photo.date_resolver import DateResolver, NullStampOcr, StampOcr
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.plugins.di import create_container


class TestPhotoProviderWiring:
    """Тесты wire-up PhotoProvider в основной DI контейнер."""

    @pytest.mark.asyncio
    async def test_create_container_resolves_file_storage(self) -> None:
        """create_container() может разрешить FileStorage в APP scope."""
        container = create_container()
        try:
            storage = await container.get(FileStorage)
            assert isinstance(storage, LocalFileStorage)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_create_container_resolves_detector_client(self) -> None:
        """create_container() может разрешить DetectorClient в APP scope."""
        container = create_container()
        try:
            detector = await container.get(DetectorClient)
            # По умолчанию (когда detector.url не задан) должен быть NullDetector
            assert isinstance(detector, NullDetector)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_create_container_resolves_stamp_ocr(self) -> None:
        """create_container() может разрешить StampOcr в APP scope."""
        container = create_container()
        try:
            ocr = await container.get(StampOcr)
            assert isinstance(ocr, NullStampOcr)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_create_container_resolves_date_resolver(self) -> None:
        """create_container() может разрешить DateResolver в APP scope."""
        container = create_container()
        try:
            resolver = await container.get(DateResolver)
            assert isinstance(resolver, DateResolver)
            # Проверяем, что OCR был внедрён
            assert resolver.ocr is not None
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_create_container_resolves_photo_repository(self) -> None:
        """create_container() может разрешить PhotoRepository в REQUEST scope."""
        container = create_container()
        try:
            async with container() as request_container:
                repo = await request_container.get(PhotoRepository)
                assert isinstance(repo, PhotoRepository)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_create_container_resolves_detection_repository(self) -> None:
        """create_container() может разрешить DetectionRepository в REQUEST scope."""
        container = create_container()
        try:
            async with container() as request_container:
                repo = await request_container.get(DetectionRepository)
                assert isinstance(repo, DetectionRepository)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_app_scope_instances_are_reused(self) -> None:
        """APP scope провайдеры переиспользуются между REQUEST контекстами."""
        container = create_container()
        try:
            async with container() as request_container1:
                resolver1 = await request_container1.get(DateResolver)

            async with container() as request_container2:
                resolver2 = await request_container2.get(DateResolver)

            # Они должны быть одинаковыми объектами (переиспользованы)
            assert resolver1 is resolver2
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_request_scope_instances_are_different(self) -> None:
        """REQUEST scope репозитории создаются новые в каждом REQUEST контексте."""
        container = create_container()
        try:
            async with container() as request_container1:
                repo1 = await request_container1.get(PhotoRepository)

            async with container() as request_container2:
                repo2 = await request_container2.get(PhotoRepository)

            # Они должны быть разными объектами (новые для каждого контекста)
            assert repo1 is not repo2
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_photo_only_container_uses_noop_recalculator(self) -> None:
        """Контейнер с только PhotoProvider (без ObservationProvider) использует Noop.

        Это доказывает graceful degradation: photo домен работает и без observation,
        когда observation не подключён в контейнер.
        """
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from dishka import make_async_container

        from app.domains.methodology.provider import MethodologyProvider
        from app.domains.photo.provider import PhotoProvider
        from app.domains.photo.recalculator import NoopObservationRecalculator
        from app.domains.photo.recalculator import ObservationRecalculator as ObsRecalc
        from app.domains.schedule.provider import ScheduleProvider
        from app.domains.site.provider import SiteProvider
        from app.domains.user.provider import UserProvider
        from app.domains.utility.provider import UtilityProvider
        from app.plugins.di import AppProvider, DatabaseProvider

        # Создаём временную директорию для storage
        with TemporaryDirectory() as tmpdir:
            storage_root = Path(tmpdir) / "storage"
            storage_root.mkdir(parents=True, exist_ok=True)

            # Строим контейнер БЕЗ ObservationProvider
            container = make_async_container(
                AppProvider(),
                DatabaseProvider(),
                UserProvider(),
                SiteProvider(),
                ScheduleProvider(),
                MethodologyProvider(),
                PhotoProvider(),  # Только PhotoProvider, без ObservationProvider
                UtilityProvider(),
            )

            try:
                async with container() as request_container:
                    recalculator = await request_container.get(ObsRecalc)
                    # Должен быть Noop, т.к. ObservationProvider() не подключён
                    assert isinstance(recalculator, NoopObservationRecalculator)
                    # Убедиться, что это точно Noop, а не Live
                    from app.domains.observation.recalculator import LiveObservationRecalculator

                    assert not isinstance(recalculator, LiveObservationRecalculator)
            finally:
                await container.close()


class TestStorageIsolation:
    """Тесты изоляции файлового хранилища между тестами.

    Доказывает, что каждый тест получает свою независимую копию storage,
    управляемую pytest's tmp_path fixture.
    """

    @pytest.mark.asyncio
    async def test_storage_first_writes_probe_file(self, storage, tmp_path) -> None:
        """Первый тест: пишет файл-зонд и проверяет его существование.

        Также проверяет, что storage.root находится под tmp_path pytest.
        """
        # Проверка: storage.root должен быть под tmp_path
        assert tmp_path in storage.root.parents or storage.root == tmp_path, (
            f"storage.root={storage.root} should be under tmp_path={tmp_path}"
        )

        # Пишем файл-зонд
        key = "isolation/probe.bin"
        await storage.put(key, b"x")

        # Проверяем, что файл существует
        exists = await storage.exists(key)
        assert exists, f"File '{key}' should exist after put()"

    @pytest.mark.asyncio
    async def test_storage_second_does_not_see_first_file(self, storage) -> None:
        """Второй тест: не видит файл первого теста (доказывает изоляцию).

        Если этот тест падает, значит storage недостаточно изолирован
        (например, если использовать общую директорию вместо tmp_path).
        """
        key = "isolation/probe.bin"
        exists = await storage.exists(key)
        assert not exists, f"File '{key}' should NOT exist (storage should be isolated per test)"
