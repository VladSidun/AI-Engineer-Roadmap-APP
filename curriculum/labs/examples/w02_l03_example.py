from collections.abc import Iterable, Iterator


def labels(lines: Iterable[str]) -> Iterator[str]:
    for line in lines:
        stripped = line.strip()
        if stripped:
            yield stripped

if __name__ == "__main__":
    source = iter([" ", " draft\n", "later"])
    print(next(labels(source)))
    print(next(source))
