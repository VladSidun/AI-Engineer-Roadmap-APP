import json
from pathlib import Path


def solve(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    count = data.get("count")
    if type(count) is not int or count < 0:
        raise ValueError("expected a non-negative integer count")
    return count
