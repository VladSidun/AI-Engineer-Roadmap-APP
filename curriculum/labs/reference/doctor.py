import json
from pathlib import Path


def check_workspace(path: Path) -> dict[str, int]:
    with path.open(encoding="utf-8") as file:
        plan = json.load(file)
    if not isinstance(plan, list):
        raise ValueError("expected a list")
    total = 0
    for item in plan:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("topic"), str)
            or not item["topic"].strip()
            or type(item.get("minutes")) is not int
            or item["minutes"] <= 0
        ):
            raise ValueError("each item needs a topic and positive minutes")
        total += item["minutes"]
    return {"items": len(plan), "minutes": total}
