import sqlite3


def join_scores(connection: sqlite3.Connection) -> list[tuple[str, int]]:
    """Join topics(id, name) and results(topic_id, score), ordered by name, then score."""
    raise NotImplementedError


def fetch_json(url: str) -> dict[str, object]:
    """GET with a two-second timeout; require a JSON object."""
    raise NotImplementedError


def test_empty_join() -> None:
    raise NotImplementedError


def test_valid_payload() -> None:
    raise NotImplementedError


def test_invalid_payload() -> None:
    raise NotImplementedError
