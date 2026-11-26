import io
import json
import sqlite3
import urllib.request
from unittest.mock import patch


def join_scores(connection: sqlite3.Connection) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = connection.execute(
        "SELECT topics.name, results.score FROM topics "
        "JOIN results ON topics.id = results.topic_id ORDER BY topics.name, results.score"
    ).fetchall()
    return result


def fetch_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=2) as response:
        data = json.load(response)
    if not isinstance(data, dict):
        raise ValueError("expected an object")
    return data


def test_empty_join() -> None:
    with sqlite3.connect(":memory:") as db:
        db.executescript("CREATE TABLE topics (id INTEGER, name TEXT);"
                         "CREATE TABLE results (topic_id INTEGER, score INTEGER);")
        assert join_scores(db) == []


def test_valid_payload() -> None:
    with patch("urllib.request.urlopen", return_value=io.BytesIO(b'{"ok": 1}')):
        assert fetch_json("http://127.0.0.1:8000") == {"ok": 1}


def test_invalid_payload() -> None:
    with patch("urllib.request.urlopen", return_value=io.BytesIO(b"[]")):
        try:
            fetch_json("http://127.0.0.1:8000")
        except ValueError:
            return
    raise AssertionError("expected ValueError")
