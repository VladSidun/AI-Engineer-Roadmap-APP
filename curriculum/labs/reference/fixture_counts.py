import json
from collections import Counter
from pathlib import Path


def count_kinds(path: Path) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("expected list")
    counts: Counter[str] = Counter()
    for row in data:
        kind = row.get("kind") if isinstance(row, dict) else None
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("expected nonempty kind")
        counts[kind] += 1
    return dict(counts)
