import json


def solve(status: int, body: bytes) -> dict[str, object] | None:
    if status == 204 and not body:
        return None
    if status not in (200, 201):
        raise ValueError('unsupported response status')
    result = json.loads(body.decode('utf-8'))
    if not isinstance(result, dict):
        raise ValueError('expected a JSON object')
    return result
