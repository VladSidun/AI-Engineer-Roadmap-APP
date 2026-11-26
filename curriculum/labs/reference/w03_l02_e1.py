import asyncio
from collections.abc import Awaitable, Callable


async def solve(fetch: Callable[[str], Awaitable[str]], keys: list[str], limit: int) -> list[str]:
    if limit < 1:
        raise ValueError('positive limit required')
    capacity = asyncio.Semaphore(limit)

    async def one(key: str) -> str:
        async with capacity:
            return await fetch(key)

    async with asyncio.TaskGroup() as group:
        results = [group.create_task(one(key)) for key in keys]
    return [result.result() for result in results]
