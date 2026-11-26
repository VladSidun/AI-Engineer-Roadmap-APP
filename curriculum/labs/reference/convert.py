import csv
import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        return 2
    source, target = map(Path, argv)
    if {source.suffix, target.suffix} != {".csv", ".json"}:
        return 2
    try:
        if source.suffix == ".csv":
            with source.open(newline="", encoding="utf-8") as file:
                raw = list(csv.DictReader(file))
        else:
            raw = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return 2
        rows = []
        for row in raw:
            if not isinstance(row, dict) or set(row) != {"name", "count"}:
                return 2
            name, count = row["name"], row["count"]
            if source.suffix == ".csv":
                count = int(count)
            if not isinstance(name, str) or not name.strip() or type(count) is not int or count < 0:
                return 2
            rows.append({"name": name, "count": count})
        if target.suffix == ".csv":
            with target.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=["name", "count"])
                writer.writeheader()
                writer.writerows(rows)
        else:
            target.write_text(json.dumps(rows, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, TypeError, ValueError, csv.Error):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
