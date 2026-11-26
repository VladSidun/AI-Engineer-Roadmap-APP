from collections.abc import Iterable


def solve(rows: Iterable[tuple[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_key, raw_title in rows:
        key, title = raw_key.strip(), raw_title.strip()
        if not key or not title:
            raise ValueError("key and title are required")
        result.setdefault(key, title)
    return result
