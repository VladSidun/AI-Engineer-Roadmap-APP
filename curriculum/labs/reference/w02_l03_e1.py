from collections.abc import Iterable, Iterator


def solve(lines: Iterable[str]) -> Iterator[tuple[str, str]]:
    for line in lines:
        if not line.strip():
            continue
        key, separator, title = line.partition("|")
        if not separator or not key.strip() or not title.strip():
            raise ValueError("expected key|title")
        yield key.strip(), title.strip()
