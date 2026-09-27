"""Тесты для recalculator.py: StatusRecalculator и NoopStatusRecalculator."""

import uuid

import pytest

from app.domains.methodology.recalculator import NoopStatusRecalculator


@pytest.mark.asyncio
class TestNoopStatusRecalculator:
    """Тесты для NoopStatusRecalculator."""

    async def test_noop_recalculate_returns_none(self):
        """NoopStatusRecalculator.recalculate(site_id) возвращает None."""
        recalculator = NoopStatusRecalculator()
        result = await recalculator.recalculate(uuid.uuid4())
        assert result is None

    async def test_noop_recalculate_multiple_calls(self):
        """NoopStatusRecalculator.recalculate() можно вызывать многократно."""
        recalculator = NoopStatusRecalculator()
        site_id_1 = uuid.uuid4()
        site_id_2 = uuid.uuid4()

        result1 = await recalculator.recalculate(site_id_1)
        result2 = await recalculator.recalculate(site_id_2)

        assert result1 is None
        assert result2 is None
