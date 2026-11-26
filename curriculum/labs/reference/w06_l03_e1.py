import math


def solve(samples: list[int | float]) -> dict[str, int | float | None]:
    if any(type(value) not in (int, float) or value < 0
           or (isinstance(value, float) and not math.isfinite(value)) for value in samples):
        raise ValueError('invalid elapsed sample')
    ordered = sorted(samples)
    count = len(ordered)
    return {'count': count,
            'p50': ordered[(count + 1) // 2 - 1] if count else None,
            'p95': ordered[(95 * count + 99) // 100 - 1] if count else None}
