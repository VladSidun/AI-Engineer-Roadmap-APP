import json
import sys
from pathlib import Path
from shutil import copyfile
from uuid import uuid4

import pytest

from app.config import ROOT
from app.domain.content import Content, Suite
from quest_runner import cli
from quest_runner.cli import RunnerError, request, run_suite

SUITES = tuple(Content().suites.values())


@pytest.mark.parametrize("suite", SUITES, ids=[suite.id for suite in SUITES])
def test_each_reference_and_broken_starter(suite: Suite, tmp_path: Path) -> None:
    destination = tmp_path / suite.starter
    copyfile(ROOT / "curriculum/labs/reference" / suite.starter, destination)
    code, cases, _ = run_suite(suite.model_dump(), tmp_path, 15)
    assert code == 0
    assert {case["id"] for case in cases} == set(suite.testIds)
    assert {case["status"] for case in cases} == {"passed"}

    copyfile(ROOT / "curriculum/labs/starters" / suite.starter, destination)
    code, cases, _ = run_suite(suite.model_dump(), tmp_path, 15)
    assert code == 1 and cases
    assert all(case["status"] == "failed" for case in cases)


@pytest.mark.parametrize("source,timeout,status", [
    ("import time\ntime.sleep(5)\n", 1, "timeout"),
    ("import pytest\npytest.skip('skip', allow_module_level=True)\n", 15, "skipped"),
    ("def invalid python syntax", 15, "error"),
])
def test_process_failure_modes(source: str, timeout: int, status: str, tmp_path: Path) -> None:
    suite = SUITES[0]
    (tmp_path / suite.starter).write_text(source, encoding="utf-8")
    code, cases, _ = run_suite(suite.model_dump(), tmp_path, timeout)
    if status == "timeout":
        assert code == 124 and not cases
    else:
        assert code == (0 if status == "skipped" else 1)
        assert {case["status"] for case in cases} == {status}


@pytest.mark.parametrize("url", ["https://127.0.0.1:8000", "http://localhost:8000", "http://127.0.0.1:8000/path"])
def test_runner_does_not_send_credentials_outside_local_api(url: str) -> None:
    with pytest.raises(RunnerError, match="loopback"):
        request(url, "synthetic-token", "/runner/reports", {})


def test_temporary_delivery_saves_and_retries_same_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = SUITES[0]
    challenge = str(uuid4())
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    copyfile(ROOT / "curriculum/labs/reference" / suite.starter, workspace / suite.starter)
    reports = tmp_path / "reports"
    attempted: list[dict[str, object]] = []
    token = "local-fixture-token"

    def send(api: str, supplied: str, path: str, body: dict[str, object]) -> dict[str, object]:
        assert supplied == token and path == "/runner/reports"
        attempted.append(body)
        if len(attempted) == 1:
            raise cli.DeliveryUnavailable("fixture unavailable")
        return {"verdict": "test_verified_local"}

    monkeypatch.setenv("QUEST_RUNNER_TOKEN", token)
    monkeypatch.setattr(cli, "request", send)
    monkeypatch.setattr(sys, "argv", [
        "quest-runner", "test", "--exercise", suite.exerciseId, "--variant", suite.variantId,
        "--workspace", str(workspace), "--challenge", challenge, "--report-dir", str(reports),
    ])
    assert cli.main() == 2
    saved, = list(reports.glob("*.json"))
    assert json.loads(saved.read_bytes()) == attempted[0]
    assert token not in saved.read_text(encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["quest-runner", "submit", "--report", str(saved)])
    assert cli.main() == 0
    assert attempted[0] == attempted[1]
