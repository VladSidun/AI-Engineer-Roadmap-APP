from collections.abc import Callable


def solve(credential: str | None, verify: Callable[[str], str | None], allow: Callable[[str], bool]) -> int:
    if credential is None or not credential.strip():
        return 401
    actor = verify(credential)
    if actor is None:
        return 401
    return 200 if allow(actor) else 403
