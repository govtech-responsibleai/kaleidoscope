"""
Tests for the gather_with_concurrency utility.
"""

import asyncio
import pytest

from src.common.concurrency import gather_with_concurrency


@pytest.mark.unit
class TestGatherWithConcurrency:
    """Tests for gather_with_concurrency."""

    def test_preserves_result_order(self):
        """Results must come back in input order, not execution order."""

        async def delayed(value, delay):
            await asyncio.sleep(delay)
            return value

        async def run():
            # Later items finish faster, but order must be preserved
            return await gather_with_concurrency(
                5,
                delayed("a", 0.03),
                delayed("b", 0.02),
                delayed("c", 0.01),
            )

        results = asyncio.run(run())
        assert results == ["a", "b", "c"]

    def test_respects_concurrency_limit(self):
        """At most `limit` coroutines should run at the same time."""
        current = 0
        max_concurrent = 0

        async def tracked():
            nonlocal current, max_concurrent
            current += 1
            max_concurrent = max(max_concurrent, current)
            await asyncio.sleep(0.01)
            current -= 1

        async def run():
            await gather_with_concurrency(3, *(tracked() for _ in range(20)))

        asyncio.run(run())
        assert max_concurrent <= 3

    def test_propagates_exceptions(self):
        """If one coroutine raises, the exception should propagate."""

        async def failing():
            raise ValueError("boom")

        async def succeeding():
            return "ok"

        async def run():
            return await gather_with_concurrency(
                5,
                succeeding(),
                failing(),
                succeeding(),
            )

        with pytest.raises(ValueError, match="boom"):
            asyncio.run(run())

    def test_limit_one_runs_sequentially(self):
        """With limit=1, coroutines should run one at a time."""
        current = 0
        max_concurrent = 0

        async def tracked(value):
            nonlocal current, max_concurrent
            current += 1
            max_concurrent = max(max_concurrent, current)
            await asyncio.sleep(0.01)
            current -= 1
            return value

        async def run():
            return await gather_with_concurrency(
                1,
                tracked(1),
                tracked(2),
                tracked(3),
            )

        results = asyncio.run(run())
        assert results == [1, 2, 3]
        assert max_concurrent == 1

    def test_empty_coroutines(self):
        """Should return an empty list when no coroutines are given."""

        async def run():
            return await gather_with_concurrency(5)

        results = asyncio.run(run())
        assert results == []

    def test_limit_greater_than_coros(self):
        """Works correctly when limit exceeds number of coroutines."""

        async def identity(value):
            return value

        async def run():
            return await gather_with_concurrency(
                100,
                identity(1),
                identity(2),
            )

        results = asyncio.run(run())
        assert results == [1, 2]
