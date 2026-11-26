"""Public M0 suites. The runner selects a fixed file and variant from its own catalog."""

import csv
import importlib.util
import io
import json
import os
import sqlite3
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

EXERCISE = os.environ["QUEST_EXERCISE"]
VARIANT = int(os.environ["QUEST_VARIANT"][1:])
FILE = Path(os.environ["QUEST_STUDENT_FILE"])
LABEL = ("", "orchid", "maple", "cedar")[VARIANT]
OTHER = ("", "lime", "jade", "iris")[VARIANT]


@pytest.fixture
def student() -> ModuleType:
    spec = importlib.util.spec_from_file_location("student", FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse(io.BytesIO):
    pass


def test_normal(student: ModuleType, tmp_path: Path) -> None:
    if EXERCISE == "W01-L03-E1":
        assert student.parse_setting(f" topic = {LABEL} ") == ("topic", LABEL)
    elif EXERCISE == "W01-L03-E2":
        path = tmp_path / "counts.json"
        path.write_text(json.dumps([{"kind": LABEL}, {"kind": OTHER}, {"kind": LABEL}]))
        assert student.count_kinds(path) == {LABEL: 2, OTHER: 1}
    elif EXERCISE == "W01-L04-E1":
        path = tmp_path / "data.json"
        path.write_text(json.dumps([{"name": LABEL, "count": VARIANT}]))
        dest = tmp_path / "result.csv"
        assert student.main([str(path), str(dest)]) == 0
        with dest.open(newline="", encoding="utf-8") as file:
            assert list(csv.DictReader(file)) == [{"name": LABEL, "count": str(VARIANT)}]
    elif EXERCISE == "G-M0-E1":
        path = tmp_path / "learning-plan.json"
        path.write_text(json.dumps([{"topic": LABEL, "minutes": VARIANT * 15}]), encoding="utf-8")
        assert student.check_workspace(path) == {"items": 1, "minutes": VARIANT * 15}
    else:
        with sqlite3.connect(":memory:") as db:
            db.executescript("CREATE TABLE topics (id INTEGER, name TEXT);"
                             "CREATE TABLE results (topic_id INTEGER, score INTEGER);")
            db.execute("INSERT INTO topics VALUES (?, ?)", (VARIANT, LABEL))
            db.execute("INSERT INTO results VALUES (?, ?)", (VARIANT, 11))
            db.execute("INSERT INTO results VALUES (?, ?)", (99, 42))
            assert student.join_scores(db) == [(LABEL, 11)]


def test_boundary(student: ModuleType, tmp_path: Path) -> None:
    if EXERCISE == "W01-L03-E1":
        assert student.parse_setting(f"key={LABEL}={OTHER}") == ("key", f"{LABEL}={OTHER}")
    elif EXERCISE == "W01-L03-E2":
        path = tmp_path / "empty.json"
        path.write_text("[]")
        assert student.count_kinds(path) == {}
    elif EXERCISE == "W01-L04-E1":
        path = tmp_path / "comma,quoted.csv"
        path.write_text(f'name,count\n"{LABEL},{OTHER}",{VARIANT}\n', encoding="utf-8")
        dest = tmp_path / "result.json"
        assert student.main([str(path), str(dest)]) == 0
        assert json.loads(dest.read_text(encoding="utf-8")) == [
            {"name": f"{LABEL},{OTHER}", "count": VARIANT}
        ]
    elif EXERCISE == "G-M0-E1":
        path = tmp_path / "empty.json"
        path.write_text("[]", encoding="utf-8")
        assert student.check_workspace(path) == {"items": 0, "minutes": 0}
    else:
        url = f"http://127.0.0.1:23456/{LABEL}"
        with patch("urllib.request.urlopen", return_value=FakeResponse(
            json.dumps({"topic": LABEL}).encode()
        )) as call:
            assert student.fetch_json(url) == {"topic": LABEL}
            call.assert_called_once_with(url, timeout=2)


def test_invalid(student: ModuleType, tmp_path: Path) -> None:
    if EXERCISE == "W01-L03-E1":
        for value in ("key", "=missing_key", "key=  "):
            with pytest.raises(ValueError):
                student.parse_setting(value)
    elif EXERCISE == "W01-L03-E2":
        path = tmp_path / "invalid.json"
        path.write_text(json.dumps([{"kind": ""}]))
        with pytest.raises(ValueError):
            student.count_kinds(path)
    elif EXERCISE == "W01-L04-E1":
        path = tmp_path / "invalid.csv"
        path.write_text(f"name,count\n{LABEL},-1\n", encoding="utf-8")
        dest = tmp_path / "result.json"
        assert student.main([str(path), str(dest)]) == 2
        assert not dest.exists()
    elif EXERCISE == "G-M0-E1":
        path = tmp_path / "invalid.json"
        for invalid_plan in ({"topic": LABEL}, [{"topic": LABEL, "minutes": True}],
                      [{"topic": " ", "minutes": 10}], [{"topic": OTHER, "minutes": 0}]):
            path.write_text(json.dumps(invalid_plan), encoding="utf-8")
            with pytest.raises(ValueError):
                student.check_workspace(path)
        with pytest.raises(FileNotFoundError):
            student.check_workspace(tmp_path / "missing.json")
    else:
        with patch("urllib.request.urlopen", return_value=FakeResponse(b"[]")):
            with pytest.raises(ValueError):
                student.fetch_json("http://127.0.0.1:23456/invalid")


def test_transfer(student: ModuleType, tmp_path: Path) -> None:
    if EXERCISE == "W01-L03-E1":
        assert student.parse_setting(f"{LABEL}=  café ") == (LABEL, "café")
    elif EXERCISE == "W01-L03-E2":
        path = tmp_path / "unicode.json"
        path.write_text(json.dumps([{"kind": "кава"}, {"kind": LABEL}]))
        assert student.count_kinds(path) == {"кава": 1, LABEL: 1}
    elif EXERCISE == "W01-L04-E1":
        source = tmp_path / "input.json"
        source.write_text(json.dumps([{"name": "кава", "count": 0}]), encoding="utf-8")
        dest = tmp_path / "output.csv"
        assert student.main([str(source), str(dest)]) == 0
        assert "кава,0" in dest.read_text(encoding="utf-8")
    elif EXERCISE == "G-M0-E1":
        path = tmp_path / "план.json"
        path.write_text(
            json.dumps([{"topic": "кава", "minutes": 7}, {"topic": OTHER, "minutes": VARIANT}],
                       ensure_ascii=False), encoding="utf-8",
        )
        assert student.check_workspace(path) == {"items": 2, "minutes": 7 + VARIANT}
    else:
        for name in ("test_empty_join", "test_valid_payload", "test_invalid_payload"):
            getattr(student, name)()
