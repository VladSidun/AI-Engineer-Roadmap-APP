"""Public local suites for M1 with deterministic synthetic fixtures."""

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, Mock

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


def w02_l01_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    assert student.solve([(f" {LABEL} ", OTHER), (LABEL, "new")]) == {LABEL: OTHER}


def w02_l01_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    assert student.solve(iter(())) == {}


def w02_l01_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        student.solve([(LABEL, OTHER), (LABEL, " ")])


def w02_l01_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    rows = iter([(LABEL, OTHER), (OTHER, LABEL), (LABEL.upper(), "distinct")])
    assert list(student.solve(rows)) == [LABEL, OTHER, LABEL.upper()]


def w02_l02_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / f"{LABEL}.json"
    path.write_text(json.dumps({"count": VARIANT, "label": OTHER}), encoding="utf-8")
    assert student.solve(path) == VARIANT


def w02_l02_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "zero.json"
    path.write_text('{"count": 0}', encoding="utf-8")
    assert student.solve(path) == 0


def w02_l02_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / f"{OTHER}.json"
    for invalid in ('{}', '[]', '{"count": true}', '{"count": "7"}', '{"count": -1}', '{"count":'):
        path.write_text(invalid, encoding="utf-8")
        with pytest.raises(ValueError):
            student.solve(path)


def w02_l02_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        student.solve(tmp_path / f"{OTHER}.json")


def w02_l03_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    assert list(student.solve([f" {LABEL} | {OTHER} "])) == [(LABEL, OTHER)]


def w02_l03_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    assert list(student.solve(iter(["", " ", "\t"]))) == []


def w02_l03_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    for invalid in (f"{LABEL}", f"|{OTHER}", f"{LABEL}| "):
        result = student.solve([f"{LABEL}|{OTHER}", invalid])
        assert next(result) == (LABEL, OTHER)
        with pytest.raises(ValueError):
            next(result)


def w02_l03_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    rows = iter([" ", f"{LABEL}|x|y", f"{OTHER}|tail"])
    assert next(student.solve(rows)) == (LABEL, "x|y")
    assert next(rows) == f"{OTHER}|tail"


def w02_l04_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    source, dest = tmp_path / "in.csv", tmp_path / "out.json"
    source.write_text(f'name,count\n"{LABEL}, {OTHER}",{VARIANT}\n', encoding="utf-8")
    assert student.solve(source, dest) == 1
    assert json.loads(dest.read_text(encoding="utf-8")) == [{"name": f"{LABEL}, {OTHER}", "count": VARIANT}]


def w02_l04_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    source, dest = tmp_path / "empty.csv", tmp_path / "empty.json"
    source.write_text("name,count\n", encoding="utf-8")
    assert student.solve(source, dest) == 0
    assert json.loads(dest.read_text(encoding="utf-8")) == []


def w02_l04_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    source, dest = tmp_path / "bad.csv", tmp_path / "existing.json"
    dest.write_text("previous", encoding="utf-8")
    for wrong in ("name,other\n", f"name,count\n{LABEL},-1", f"name,count\n{LABEL}", f"name,count\n{LABEL},1,extra"):
        source.write_text(wrong, encoding="utf-8")
        with pytest.raises(ValueError):
            student.solve(source, dest)
        assert dest.read_text(encoding="utf-8") == "previous"


def w02_l04_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    source, dest = tmp_path / "input.csv", tmp_path / "list.json"
    source.write_text(f"name,count\n {OTHER} ,0\n {LABEL} ,12\n", encoding="utf-8")
    assert student.solve(source, dest) == 2
    assert json.loads(dest.read_text(encoding="utf-8")) == [{"name": OTHER, "count": 0}, {"name": LABEL, "count": 12}]


def w03_l01_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    assert student.solve(201, json.dumps({'key': LABEL}).encode()) == {'key': LABEL}


def w03_l01_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    assert student.solve(204, b'') is None


def w03_l01_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    for status, body in [(200, b'{'), (200, b'[]'), (204, b'{}'), (403, b'{}')]:
        with pytest.raises(ValueError):
            student.solve(status, body)


def w03_l01_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    payload = {'key': OTHER, 'count': VARIANT, 'result': None}
    assert student.solve(200, json.dumps(payload).encode()) == payload


def w03_l02_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    async def fetch(key: str) -> str:
        await asyncio.sleep(0)
        return key.upper()
    assert asyncio.run(student.solve(fetch, [LABEL, OTHER, LABEL], 2)) == [LABEL.upper(), OTHER.upper(), LABEL.upper()]


def w03_l02_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    async def unused(key: str) -> str:
        pytest.fail('empty input started IO')
    assert asyncio.run(student.solve(unused, [], VARIANT)) == []


def w03_l02_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        asyncio.run(student.solve(None, [LABEL], 0))


def w03_l02_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    active = peak = 0
    async def fetch(key: str) -> str:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return key
    keys = [LABEL, OTHER] * 4
    assert asyncio.run(student.solve(fetch, keys, VARIANT)) == keys
    assert peak == VARIANT


def w03_l03_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    send = AsyncMock(side_effect=[(503, OTHER), (200, LABEL)])
    sleep = AsyncMock()
    assert asyncio.run(student.solve('GET', send, sleep, 2)) == (200, LABEL)
    sleep.assert_awaited_once_with(0.1)


def w03_l03_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    send = AsyncMock(return_value=(503, LABEL))
    sleep = AsyncMock()
    assert asyncio.run(student.solve('POST', send, sleep, 3)) == (503, LABEL)
    assert send.await_count == 1
    sleep.assert_not_awaited()


def w03_l03_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        asyncio.run(student.solve('GET', AsyncMock(), AsyncMock(), 0))
    send = AsyncMock(side_effect=TimeoutError)
    with pytest.raises(TimeoutError):
        asyncio.run(student.solve('GET', send, AsyncMock(), VARIANT))
    assert send.await_count == VARIANT


def w03_l03_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    send = AsyncMock(side_effect=[TimeoutError(), (429, OTHER), (201, LABEL)])
    sleep = AsyncMock()
    assert asyncio.run(student.solve('POST', send, sleep, 3, LABEL)) == (201, LABEL)
    assert [call.args for call in send.await_args_list] == [(LABEL,)] * 3
    assert [call.args for call in sleep.await_args_list] == [(0.1,), (0.2,)]


def w03_l04_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    events: list[dict[str, str]] = []
    assert student.solve(LABEL, lambda: json.dumps({'id': OTHER}), events.append) == {'id': OTHER}
    assert events == [{'request_id': LABEL, 'outcome': 'ok'}]


def w03_l04_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    events: list[dict[str, str]] = []
    assert student.solve(LABEL, lambda: '{}', events.append) == {}
    assert events == [{'request_id': LABEL, 'outcome': 'ok'}]


def w03_l04_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    for raw in (f'broken {OTHER}', '[]', 'null'):
        events: list[dict[str, str]] = []
        assert student.solve(LABEL, lambda: raw, events.append) is None
        assert events == [{'request_id': LABEL, 'outcome': 'invalid_response'}]


def w03_l04_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    events: list[dict[str, str]] = []
    fetch = Mock(side_effect=TimeoutError(OTHER))
    assert student.solve(LABEL, fetch, events.append) is None
    fetch.assert_called_once_with()
    assert events == [{'request_id': LABEL, 'outcome': 'timeout'}]


def g_m1_e1_normal(student: ModuleType, tmp_path: Path) -> None:
    seen: dict[str, int] = {}
    async def fetch(key: str) -> int:
        seen[key] = seen.get(key, 0) + 1
        return 503 if key == LABEL and seen[key] == 1 else 200 if key == LABEL else 404
    assert list(asyncio.run(student.solve([f' {LABEL} ', LABEL, OTHER], fetch, VARIANT)).items()) == [(LABEL, 200), (OTHER, 404)]
    assert seen == {LABEL: 2, OTHER: 1}


def g_m1_e1_boundary(student: ModuleType, tmp_path: Path) -> None:
    fetch = AsyncMock()
    assert asyncio.run(student.solve([], fetch, 1)) == {}
    fetch.assert_not_awaited()


def g_m1_e1_invalid(student: ModuleType, tmp_path: Path) -> None:
    fetch = AsyncMock()
    for keys, capacity in [([LABEL, ' '], 1), ([LABEL], 0)]:
        with pytest.raises(ValueError):
            asyncio.run(student.solve(keys, fetch, capacity))
    fetch.assert_not_awaited()


def g_m1_e1_transfer(student: ModuleType, tmp_path: Path) -> None:
    active = peak = calls = 0
    async def fetch(key: str) -> int:
        nonlocal active, peak, calls
        active += 1
        calls += 1
        peak = max(active, peak)
        await asyncio.sleep(.005)
        active -= 1
        return 503
    keys = [f'{LABEL}{i}' for i in range(6)]
    assert asyncio.run(student.solve(keys, fetch, VARIANT)) == dict.fromkeys(keys, 503)
    assert peak == VARIANT and calls == 12


CASES = {
    "W02-L01-E1": (w02_l01_e1_normal, w02_l01_e1_boundary, w02_l01_e1_invalid, w02_l01_e1_transfer),
    "W02-L02-E1": (w02_l02_e1_normal, w02_l02_e1_boundary, w02_l02_e1_invalid, w02_l02_e1_transfer),
    "W02-L03-E1": (w02_l03_e1_normal, w02_l03_e1_boundary, w02_l03_e1_invalid, w02_l03_e1_transfer),
    "W02-L04-E1": (w02_l04_e1_normal, w02_l04_e1_boundary, w02_l04_e1_invalid, w02_l04_e1_transfer),
    "W03-L01-E1": (w03_l01_e1_normal, w03_l01_e1_boundary, w03_l01_e1_invalid, w03_l01_e1_transfer),
    "W03-L02-E1": (w03_l02_e1_normal, w03_l02_e1_boundary, w03_l02_e1_invalid, w03_l02_e1_transfer),
    "W03-L03-E1": (w03_l03_e1_normal, w03_l03_e1_boundary, w03_l03_e1_invalid, w03_l03_e1_transfer),
    "W03-L04-E1": (w03_l04_e1_normal, w03_l04_e1_boundary, w03_l04_e1_invalid, w03_l04_e1_transfer),
    "G-M1-E1": (g_m1_e1_normal, g_m1_e1_boundary, g_m1_e1_invalid, g_m1_e1_transfer),
}


def test_normal(student: ModuleType, tmp_path: Path) -> None:
    CASES[EXERCISE][0](student, tmp_path)


def test_boundary(student: ModuleType, tmp_path: Path) -> None:
    CASES[EXERCISE][1](student, tmp_path)


def test_invalid(student: ModuleType, tmp_path: Path) -> None:
    CASES[EXERCISE][2](student, tmp_path)


def test_transfer(student: ModuleType, tmp_path: Path) -> None:
    CASES[EXERCISE][3](student, tmp_path)
