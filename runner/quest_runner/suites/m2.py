"""Public local suites for M2 with deterministic synthetic fixtures."""

import importlib.util
import io
import json
import os
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import Mock

import pytest

EXERCISE = os.environ["QUEST_EXERCISE"]
VARIANT = int(os.environ["QUEST_VARIANT"][1:])
FILE = Path(os.environ["QUEST_STUDENT_FILE"])
LABEL = ("", "birch", "invoice", "policy")[VARIANT]
OTHER = ("", "coral", "request", "receipt")[VARIANT]


@pytest.fixture
def student() -> ModuleType:
    spec = importlib.util.spec_from_file_location("student", FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def fixture_documents(first: str, second: str) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(":memory:")) as db:
        db.executescript(
            "CREATE TABLE documents(id INTEGER PRIMARY KEY, tenant TEXT);"
            "CREATE TABLE jobs(id INTEGER PRIMARY KEY, document_id INTEGER, state TEXT);"
        )
        with db:
            db.executemany("INSERT INTO documents VALUES (?,?)", [
                (VARIANT + 30, first), (VARIANT + 60, second), (VARIANT, first)
            ])
            db.executemany("INSERT INTO jobs(document_id,state) VALUES (?,?)", [
                (VARIANT, "succeeded"), (VARIANT, "succeeded"), (VARIANT, "failed"),
                (VARIANT + 30, "queued"), (VARIANT + 60, "succeeded"),
            ])
        yield db


@contextmanager
def transaction_db() -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(":memory:")) as db:
        db.executescript(
            "CREATE TABLE documents(id INTEGER PRIMARY KEY, title TEXT NOT NULL);"
            "CREATE TABLE jobs(key TEXT PRIMARY KEY, document_id INTEGER NOT NULL);"
        )
        yield db


@contextmanager
def access_db() -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE documents(id INTEGER PRIMARY KEY, tenant TEXT, owner TEXT, title TEXT)")
        with db:
            db.executemany("INSERT INTO documents VALUES (?,?,?,?)", [
                (VARIANT, LABEL, "owner", "original"), (VARIANT + 60, OTHER, "owner", "other"),
            ])
        yield db


@contextmanager
def jobs_db() -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute(
            "CREATE TABLE jobs(id INTEGER PRIMARY KEY, document_id INTEGER, "
            "op_key TEXT, status TEXT, UNIQUE(document_id, op_key))"
        )
        yield db


@contextmanager
def gate_db() -> Iterator[sqlite3.Connection]:
    with jobs_db() as db:
        db.execute("CREATE TABLE documents(id INTEGER PRIMARY KEY, tenant TEXT)")
        with db:
            db.executemany("INSERT INTO documents VALUES (?,?)", [
                (VARIANT, LABEL), (VARIANT + 60, OTHER),
            ])
        yield db


class ShortStream(io.BytesIO):
    def read(self, size: int | None = -1, /) -> bytes:
        return super().read(size if size is None else min(size, 3))


def compose_fixture(name: str) -> dict[str, Any]:
    return {
        "services": {
            "api": {"depends_on": {"db": {"condition": "service_healthy"}}},
            "db": {"volumes": [{"type": "volume", "source": name, "target": "/var/lib/postgresql/data"}]},
        },
        "volumes": {name: {}},
    }


def w04_l01_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    with fixture_documents(LABEL, OTHER) as db:
        assert student.solve(db, LABEL) == [(VARIANT, 2), (VARIANT + 30, 0)]


def w04_l01_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    with fixture_documents(LABEL, OTHER) as db:
        assert student.solve(db, 'absent') == []


def w04_l01_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    with fixture_documents(LABEL, OTHER) as db:
        assert student.solve(db, LABEL + ' unavailable') == []
        assert db.execute('SELECT COUNT(*) FROM documents').fetchone() == (3,)


def w04_l01_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    with fixture_documents(LABEL, OTHER) as db:
        assert student.solve(db, OTHER) == [(VARIANT + 60, 1)]


def w04_l02_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    with transaction_db() as db:
        identity = student.solve(db, LABEL, OTHER)
        assert db.execute('SELECT title FROM documents WHERE id = ?', (identity,)).fetchone() == (LABEL,)
        assert db.execute('SELECT document_id FROM jobs').fetchone() == (identity,)


def w04_l02_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    with transaction_db() as db:
        student.solve(db, f'{LABEL} note', OTHER)
        assert not db.in_transaction


def w04_l02_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    with transaction_db() as db:
        for title, key in [(' ', OTHER), (LABEL, '')]:
            with pytest.raises(ValueError):
                student.solve(db, title, key)
        assert db.execute('SELECT COUNT(*) FROM documents').fetchone() == (0,)


def w04_l02_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    with transaction_db() as db:
        student.solve(db, LABEL, OTHER)
        with pytest.raises(sqlite3.IntegrityError):
            student.solve(db, 'second', OTHER)
        assert db.execute('SELECT title FROM documents').fetchall() == [(LABEL,)]
        assert not db.in_transaction


def w04_l03_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    fetch = Mock(return_value={'id': VARIANT, 'title': LABEL, 'private_path': OTHER})
    assert student.solve(VARIANT, fetch) == (200, {'id': VARIANT, 'title': LABEL})
    fetch.assert_called_once_with(VARIANT)


def w04_l03_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    fetch = Mock(return_value=None)
    assert student.solve(VARIANT + 100, fetch) == (404, {'code': 'not_found'})


def w04_l03_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    fetch = Mock()
    for invalid in (0, -VARIANT, True, str(VARIANT), float(VARIANT)):
        assert student.solve(invalid, fetch) == (422, {'code': 'invalid_id'})
    fetch.assert_not_called()


def w04_l03_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    fetch = Mock(side_effect=OSError(OTHER))
    with pytest.raises(OSError):
        student.solve(VARIANT, fetch)


def w04_l04_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    with fixture_documents(LABEL, OTHER) as db:
        assert student.solve(db, LABEL, 0, 1) == ([VARIANT], VARIANT)
        assert student.solve(db, LABEL, VARIANT, 1) == ([VARIANT + 30], None)


def w04_l04_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    with fixture_documents(LABEL, OTHER) as db:
        assert student.solve(db, LABEL, 0, 2) == ([VARIANT, VARIANT + 30], None)
        assert student.solve(db, LABEL, VARIANT + 40, 50) == ([], None)


def w04_l04_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    with fixture_documents(LABEL, OTHER) as db:
        for after, limit in [(-1, 10), (0, 0), (0, 51), (True, 1), (0, False)]:
            with pytest.raises(ValueError):
                student.solve(db, LABEL, after, limit)


def w04_l04_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    with fixture_documents(LABEL, OTHER) as db:
        assert student.solve(db, OTHER, 0, VARIANT) == ([VARIANT + 60], None)
        assert student.solve(db, LABEL, VARIANT + 30, 1) == ([], None)


def w05_l01_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    verify, allow = Mock(return_value=LABEL), Mock(return_value=True)
    assert student.solve(OTHER, verify, allow) == 200
    verify.assert_called_once_with(OTHER)
    allow.assert_called_once_with(LABEL)


def w05_l01_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    verify, allow = Mock(), Mock()
    assert student.solve(None, verify, allow) == student.solve('  ', verify, allow) == 401
    verify.assert_not_called()
    allow.assert_not_called()


def w05_l01_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    verify, allow = Mock(return_value=None), Mock()
    assert student.solve(LABEL, verify, allow) == 401
    allow.assert_not_called()


def w05_l01_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    verify, allow = Mock(return_value=OTHER), Mock(return_value=False)
    assert student.solve(LABEL, verify, allow) == 403
    allow.assert_called_once_with(OTHER)


def w05_l02_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    assert student.solve('editor', LABEL, OTHER, LABEL, OTHER, 'update') is True
    assert student.solve('editor', LABEL, OTHER, 'different', OTHER, 'update') is False


def w05_l02_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    assert student.solve('viewer', LABEL, OTHER, 'different', OTHER, 'read') is True
    assert student.solve('viewer', LABEL, OTHER, LABEL, OTHER, 'delete') is False


def w05_l02_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    for role, actor, tenant, action in [('admin', LABEL, OTHER, 'publish'), ('guest', LABEL, OTHER, 'read'), ('admin', '', OTHER, 'read'), ('admin', LABEL, ' ', 'read')]:
        doc_tenant = tenant
        assert student.solve(role, actor, tenant, LABEL, doc_tenant, action) is False


def w05_l02_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    for action in ('read', 'update', 'delete'):
        assert student.solve('admin', LABEL, OTHER, LABEL, LABEL, action) is False
        assert student.solve('admin', LABEL, OTHER, 'different', OTHER, action) is True


def w05_l03_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    data = json.dumps({'title': f' {LABEL} '}).encode()
    assert student.solve(io.BytesIO(data), 'application/json', len(data) + VARIANT) == LABEL


def w05_l03_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    data = json.dumps({'title': LABEL}).encode()
    assert student.solve(ShortStream(data), 'application/json', len(data)) == LABEL


def w05_l03_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    for data in (b'[]', b'{}', b'{', bytes([255]), b'{"title":true}', b'{"title":" "}'):
        with pytest.raises(ValueError):
            student.solve(io.BytesIO(data), 'application/json', 64)
    stream = Mock()
    for media, limit in [('text/plain', 10), ('application/json', 0), ('application/json', True)]:
        with pytest.raises(ValueError):
            student.solve(stream, media, limit)
    stream.read.assert_not_called()


def w05_l03_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    data = json.dumps({'title': OTHER}).encode()
    stream = ShortStream(data + b' ' * 100)
    with pytest.raises(ValueError):
        student.solve(stream, 'application/json', len(data))
    assert stream.tell() == len(data) + 1


def w05_l04_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    with access_db() as db:
        assert student.solve(db, VARIANT, LABEL, 'owner', 'changed') == 200
        assert db.execute('SELECT title FROM documents ORDER BY id').fetchall() == [('changed',), ('other',)]
        assert not db.in_transaction


def w05_l04_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    with access_db() as db:
        assert student.solve(db, VARIANT + 50, LABEL, 'owner', 'changed') == 404
        assert db.execute('SELECT title FROM documents ORDER BY id').fetchall() == [('original',), ('other',)]


def w05_l04_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    with access_db() as db:
        assert student.solve(db, VARIANT, LABEL, 'owner', ' ') == 422
        assert db.execute('SELECT title FROM documents WHERE id = ?', (VARIANT,)).fetchone() == ('original',)


def w05_l04_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    with access_db() as db:
        assert student.solve(db, VARIANT, OTHER, 'owner', 'changed') == 404
        assert student.solve(db, VARIANT, LABEL, 'viewer', 'changed') == 404
        assert db.execute('SELECT title FROM documents ORDER BY id').fetchall() == [('original',), ('other',)]


def w06_l01_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    config = compose_fixture(LABEL)
    assert student.solve(config) is True


def w06_l01_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    config = compose_fixture(OTHER)
    config['services']['db']['ports'] = []
    assert student.solve(config) is True


def w06_l01_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    invalid_configs: tuple[object, ...] = (None, {}, {'services': []}, {'services': {'db': {}, 'api': []}})
    for invalid in invalid_configs:
        assert student.solve(invalid) is False
    config = compose_fixture(LABEL)
    config['volumes'].clear()
    assert student.solve(config) is False


def w06_l01_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    config = compose_fixture(LABEL)
    config['services']['db']['ports'] = [{'target': 5432}]
    assert student.solve(config) is False
    config = compose_fixture(OTHER)
    config['services']['api']['depends_on']['db']['condition'] = 'service_started'
    assert student.solve(config) is False


def w06_l02_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    with jobs_db() as db:
        result = student.solve(db, VARIANT, LABEL)
        assert result[1] == 'queued'
        assert db.execute('SELECT id, document_id, op_key FROM jobs').fetchone() == (result[0], VARIANT, LABEL)
        assert not db.in_transaction


def w06_l02_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    with jobs_db() as db:
        first = student.solve(db, VARIANT, LABEL)
        assert student.solve(db, VARIANT, LABEL) == first
        assert db.execute('SELECT COUNT(*) FROM jobs').fetchone() == (1,)


def w06_l02_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    with jobs_db() as db:
        for identity, key in [(0, LABEL), (True, LABEL), (VARIANT, ' ')]:
            with pytest.raises(ValueError):
                student.solve(db, identity, key)
        assert db.execute('SELECT COUNT(*) FROM jobs').fetchone() == (0,)


def w06_l02_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    with jobs_db() as db:
        first = student.solve(db, VARIANT, LABEL)[0]
        with db:
            db.execute("UPDATE jobs SET status = 'succeeded' WHERE id = ?", (first,))
        assert student.solve(db, VARIANT, LABEL) == (first, 'succeeded')
        assert student.solve(db, VARIANT + 1, LABEL)[0] != first


def w06_l03_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    samples = [8 * VARIANT, 0, 1, 2, 4]
    assert student.solve(samples) == {'count': 5, 'p50': 2, 'p95': 8 * VARIANT}
    assert samples == [8 * VARIANT, 0, 1, 2, 4]


def w06_l03_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    assert student.solve([]) == {'count': 0, 'p50': None, 'p95': None}
    assert student.solve([0.5]) == {'count': 1, 'p50': 0.5, 'p95': 0.5}


def w06_l03_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    for invalid in (False, -VARIANT, float('nan'), float('inf'), LABEL):
        with pytest.raises(ValueError):
            student.solve([2, invalid])


def w06_l03_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    samples = list(range(20 * VARIANT, 0, -1))
    assert student.solve(samples) == {'count': 20 * VARIANT, 'p50': 10 * VARIANT, 'p95': 19 * VARIANT}


def w06_l04_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    trace = [(LABEL, state) for state in ('queued', 'running', 'running', 'succeeded')]
    assert student.solve(trace) == {LABEL: 'succeeded'}


def w06_l04_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    assert student.solve(iter(())) == {}
    assert student.solve([(OTHER, 'queued')] * VARIANT) == {OTHER: 'queued'}


def w06_l04_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    for trace in ([(LABEL, 'running')], [(LABEL, 'queued'), (LABEL, 'succeeded')], [('', 'queued')], [(LABEL, 'unknown')]):
        with pytest.raises(ValueError):
            student.solve(trace)


def w06_l04_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    trace = [(LABEL, 'queued'), (OTHER, 'queued'), (OTHER, 'running'), (LABEL, 'running'), (OTHER, 'failed'), (LABEL, 'succeeded')]
    assert list(student.solve(iter(trace)).items()) == [(LABEL, 'succeeded'), (OTHER, 'failed')]
    with pytest.raises(ValueError):
        student.solve(trace + [(LABEL, 'running')])


def g_m2_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    with gate_db() as db:
        initial = student.solve(db, VARIANT, LABEL, OTHER)
        assert initial[0] == 202 and initial[2] == 'queued'
        assert db.execute('SELECT id, document_id, op_key FROM jobs').fetchall() == [(initial[1], VARIANT, OTHER)]
        assert not db.in_transaction


def g_m2_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    with gate_db() as db:
        assert student.solve(db, VARIANT + 100, LABEL, OTHER) == (404, None, None)
        assert student.solve(db, VARIANT, OTHER, 'new') == (404, None, None)
        assert db.execute('SELECT COUNT(*) FROM jobs').fetchone() == (0,)


def g_m2_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    with gate_db() as db:
        for identity, tenant, key in [(True,LABEL,OTHER), (0,LABEL,OTHER), (VARIANT,' ',OTHER), (VARIANT,LABEL,' ')]:
            assert student.solve(db, identity, tenant, key) == (422, None, None)
        assert db.execute('SELECT COUNT(*) FROM jobs').fetchone() == (0,)


def g_m2_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    with gate_db() as db:
        first = student.solve(db, VARIANT, LABEL, OTHER)[1]
        with db:
            db.execute("UPDATE jobs SET status = 'succeeded' WHERE id = ?", (first,))
        assert student.solve(db, VARIANT, OTHER, OTHER) == (404, None, None)
        assert student.solve(db, VARIANT, LABEL, OTHER) == (200, first, 'succeeded')
        second = student.solve(db, VARIANT + 60, OTHER, OTHER)
        assert second[0] == 202 and second[1] != first
        assert db.execute('SELECT COUNT(*) FROM jobs').fetchone() == (2,)


CASES = {
    "W04-L01-E1": (w04_l01_e1_normal, w04_l01_e1_boundary, w04_l01_e1_invalid, w04_l01_e1_transfer),
    "W04-L02-E1": (w04_l02_e1_normal, w04_l02_e1_boundary, w04_l02_e1_invalid, w04_l02_e1_transfer),
    "W04-L03-E1": (w04_l03_e1_normal, w04_l03_e1_boundary, w04_l03_e1_invalid, w04_l03_e1_transfer),
    "W04-L04-E1": (w04_l04_e1_normal, w04_l04_e1_boundary, w04_l04_e1_invalid, w04_l04_e1_transfer),
    "W05-L01-E1": (w05_l01_e1_normal, w05_l01_e1_boundary, w05_l01_e1_invalid, w05_l01_e1_transfer),
    "W05-L02-E1": (w05_l02_e1_normal, w05_l02_e1_boundary, w05_l02_e1_invalid, w05_l02_e1_transfer),
    "W05-L03-E1": (w05_l03_e1_normal, w05_l03_e1_boundary, w05_l03_e1_invalid, w05_l03_e1_transfer),
    "W05-L04-E1": (w05_l04_e1_normal, w05_l04_e1_boundary, w05_l04_e1_invalid, w05_l04_e1_transfer),
    "W06-L01-E1": (w06_l01_e1_normal, w06_l01_e1_boundary, w06_l01_e1_invalid, w06_l01_e1_transfer),
    "W06-L02-E1": (w06_l02_e1_normal, w06_l02_e1_boundary, w06_l02_e1_invalid, w06_l02_e1_transfer),
    "W06-L03-E1": (w06_l03_e1_normal, w06_l03_e1_boundary, w06_l03_e1_invalid, w06_l03_e1_transfer),
    "W06-L04-E1": (w06_l04_e1_normal, w06_l04_e1_boundary, w06_l04_e1_invalid, w06_l04_e1_transfer),
    "G-M2-E1": (g_m2_e1_normal, g_m2_e1_boundary, g_m2_e1_invalid, g_m2_e1_transfer),
}


def test_normal(student: ModuleType, tmp_path: Path) -> None:
    CASES[EXERCISE][0](student, tmp_path)


def test_boundary(student: ModuleType, tmp_path: Path) -> None:
    CASES[EXERCISE][1](student, tmp_path)


def test_invalid(student: ModuleType, tmp_path: Path) -> None:
    CASES[EXERCISE][2](student, tmp_path)


def test_transfer(student: ModuleType, tmp_path: Path) -> None:
    CASES[EXERCISE][3](student, tmp_path)
