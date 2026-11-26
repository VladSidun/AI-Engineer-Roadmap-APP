from collections.abc import Iterable


def solve(events: Iterable[tuple[str, str]]) -> dict[str, str]:
    transitions = {None: {'queued'}, 'queued': {'running'},
                   'running': {'succeeded', 'failed'}, 'succeeded': set(), 'failed': set()}
    latest: dict[str, str] = {}
    for identity, state in events:
        if not identity.strip():
            raise ValueError('missing job id')
        previous = latest.get(identity)
        if state != previous and state not in transitions[previous]:
            raise ValueError('invalid job transition')
        latest[identity] = state
    return latest
