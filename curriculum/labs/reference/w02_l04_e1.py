import csv
import json
from pathlib import Path


def solve(source: Path, destination: Path) -> int:
    normalized = []
    with source.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["name", "count"]:
            raise ValueError("expected name,count")
        for row in reader:
            name = row["name"]
            count = row["count"]
            if None in row or name is None or count is None or not name.strip():
                raise ValueError("expected name and count")
            value = int(count)
            if value < 0:
                raise ValueError("count must be positive or zero")
            normalized.append({"name": name.strip(), "count": value})
    destination.write_text(json.dumps(normalized, ensure_ascii=False), encoding="utf-8")
    return len(normalized)
