import asyncio
from collections.abc import Awaitable, Callable


async def solve(keys: list[str], fetch: Callable[[str], Awaitable[int]], limit: int) -> dict[str, int]:
    clean = list(dict.fromkeys(key.strip() for key in keys))
    if limit < 1 or '' in clean:
        raise ValueError('keys and positive limit required')
    capacity = asyncio.Semaphore(limit)

    async def probe(key: str) -> int:
        async with capacity:
            status = await fetch(key)
            return await fetch(key) if status == 503 else status

    async with asyncio.TaskGroup() as group:
        scheduled = {key: group.create_task(probe(key)) for key in clean}
    return {key: request.result() for key, request in scheduled.items()}
