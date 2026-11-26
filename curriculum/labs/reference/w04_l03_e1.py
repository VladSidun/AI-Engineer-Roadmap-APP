from collections.abc import Callable, Mapping


def solve(document_id: object, fetch: Callable[[int], Mapping[str, object] | None]) -> tuple[int, dict[str, object]]:
    if type(document_id) is not int or document_id < 1:
        return 422, {'code': 'invalid_id'}
    row = fetch(document_id)
    if row is None:
        return 404, {'code': 'not_found'}
    return 200, {'id': row['id'], 'title': row['title']}
