"""Tests for photo domain startup checks."""

import logging

import pytest

from app.adapters.ml.base import DetectorInfo
from app.domains.photo.startup import check_detector_classes
from tests.fakes import FakeDetector


class TestCheckDetectorClasses:
    """Tests for check_detector_classes startup function."""

    @pytest.mark.asyncio
    async def test_matching_sets_no_warning(self, caplog):
        """Matching sets (incl. *_unknown present in both) → no warning."""
        detector = FakeDetector(
            info=DetectorInfo(
                model_version="test_v1",
                class_names=("crane", "excavator_crawler", "excavator_unknown"),
                conf_threshold=0.25,
                device="cpu",
                contract="detect/v1",
            )
        )

        # Mock catalog with matching codes
        class MockCatalog:
            async def all(self):
                return [
                    type("Equipment", (), {"code": "crane", "is_coarse": False})(),
                    type("Equipment", (), {"code": "excavator_crawler", "is_coarse": False})(),
                    type("Equipment", (), {"code": "excavator_unknown", "is_coarse": True})(),
                ]

        catalog = MockCatalog()

        with caplog.at_level(logging.WARNING):
            await check_detector_classes(detector, catalog)

        # Should not log any warnings
        assert not any("Несоответствие" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_extra_model_class_warning(self, caplog):
        """Extra model class → warning names it."""
        detector = FakeDetector(
            info=DetectorInfo(
                model_version="test_v1",
                class_names=("crane", "unknown_class", "excavator_crawler"),
                conf_threshold=0.25,
                device="cpu",
                contract="detect/v1",
            )
        )

        class MockCatalog:
            async def all(self):
                return [
                    type("Equipment", (), {"code": "crane", "is_coarse": False})(),
                    type("Equipment", (), {"code": "excavator_crawler", "is_coarse": False})(),
                ]

        catalog = MockCatalog()

        with caplog.at_level(logging.WARNING):
            await check_detector_classes(detector, catalog)

        # Should log warning mentioning unknown_class
        assert any("unknown_class" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_missing_non_coarse_code_warning(self, caplog):
        """Missing non-coarse code → warning names it."""
        detector = FakeDetector(
            info=DetectorInfo(
                model_version="test_v1",
                class_names=("crane",),
                conf_threshold=0.25,
                device="cpu",
                contract="detect/v1",
            )
        )

        class MockCatalog:
            async def all(self):
                return [
                    type("Equipment", (), {"code": "crane", "is_coarse": False})(),
                    type("Equipment", (), {"code": "excavator_crawler", "is_coarse": False})(),
                    type("Equipment", (), {"code": "coarse_type", "is_coarse": True})(),
                ]

        catalog = MockCatalog()

        with caplog.at_level(logging.WARNING):
            await check_detector_classes(detector, catalog)

        # Should log warning mentioning excavator_crawler (missing non-coarse)
        # Should NOT mention coarse_type (missing coarse is OK)
        assert any("excavator_crawler" in record.message for record in caplog.records)
        assert not any("coarse_type" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_info_none_logs_info(self, caplog):
        """Info None → logs info, no warning."""
        detector = FakeDetector(info=None)

        class MockCatalog:
            async def all(self):
                return []

        catalog = MockCatalog()

        with caplog.at_level(logging.INFO):
            await check_detector_classes(detector, catalog)

        # Should log info message about ML unavailable
        assert any("ML недоступен" in record.message for record in caplog.records)
        # Should not log warning
        assert not any("Несоответствие" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_timeout_no_exception(self, caplog):
        """Timeout → no exception, continues gracefully."""
        # Create a detector that will timeout
        import asyncio

        class TimeoutDetector:
            @property
            def configured(self):
                return True

            async def info(self):
                await asyncio.sleep(10)  # Will timeout
                return None

        detector = TimeoutDetector()

        class MockCatalog:
            async def all(self):
                return []

        catalog = MockCatalog()

        # Should not raise exception
        with caplog.at_level(logging.WARNING):
            await check_detector_classes(detector, catalog)

        # Should continue without exception
        assert True  # If we get here, no exception was raised

    @pytest.mark.asyncio
    async def test_info_raising_no_exception(self, caplog):
        """Info raising exception → no exception, continues gracefully."""

        class ErrorDetector:
            @property
            def configured(self):
                return True

            async def info(self):
                raise ValueError("Connection failed")

        detector = ErrorDetector()

        class MockCatalog:
            async def all(self):
                return []

        catalog = MockCatalog()

        # Should not raise exception
        with caplog.at_level(logging.WARNING):
            await check_detector_classes(detector, catalog)

        # Should continue without exception
        assert True  # If we get here, no exception was raised
