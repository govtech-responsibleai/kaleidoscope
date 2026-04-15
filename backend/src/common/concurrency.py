"""
Concurrency utilities for bounding parallel async work.
"""

import asyncio
from typing import Any, Coroutine, List


async def gather_with_concurrency(limit: int, *coros: Coroutine) -> List[Any]:
    """
    Like asyncio.gather() but limits the number of concurrently running coroutines.

    Args:
        limit: Maximum number of coroutines running at the same time.
        *coros: Coroutines to execute.

    Returns:
        List of results in the same order as the input coroutines.
    """
    if limit < 1:
        raise ValueError("Concurrency limit must be at least 1")

    semaphore = asyncio.Semaphore(limit)

    async def sem_coro(coro: Coroutine) -> Any:
        async with semaphore:
            return await coro

    return await asyncio.gather(*(sem_coro(c) for c in coros))
