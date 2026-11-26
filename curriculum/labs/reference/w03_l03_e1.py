from collections.abc import Awaitable, Callable


async def solve(method: str, send: Callable[[str | None], Awaitable[tuple[int, str]]],
                sleep: Callable[[float], Awaitable[None]], attempts: int,
                key: str | None = None) -> tuple[int, str]:
    if not 1 <= attempts <= 5:
        raise ValueError('attempts must be between 1 and 5')
    repeatable = method == 'GET' or (method == 'POST' and bool(key))
    for index in range(attempts):
        can_retry = repeatable and index + 1 < attempts
        try:
            response = await send(key)
        except TimeoutError:
            if not can_retry:
                raise
        else:
            if not can_retry or response[0] not in {429, 502, 503, 504}:
                return response
        await sleep(0.1 * 2 ** index)
    raise AssertionError('last attempt must return or raise')
