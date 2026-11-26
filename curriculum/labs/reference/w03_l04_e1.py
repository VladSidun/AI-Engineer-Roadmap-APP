import json
from collections.abc import Callable


def solve(request_id: str, fetch: Callable[[], str], emit: Callable[[dict[str, str]], None]) -> dict[str, object] | None:
    value = None
    try:
        value = json.loads(fetch())
    except TimeoutError:
        outcome = 'timeout'
    except json.JSONDecodeError:
        outcome = 'invalid_response'
    else:
        outcome = 'ok' if isinstance(value, dict) else 'invalid_response'
    emit({'request_id': request_id, 'outcome': outcome})
    return value if isinstance(value, dict) else None
