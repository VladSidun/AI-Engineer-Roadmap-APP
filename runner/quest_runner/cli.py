import argparse
import hashlib
import http.client
import json
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import UUID, uuid4

SUITES = Path(__file__).resolve().parent / "suites"
VERSION = "1.0.0"


class RunnerError(Exception):
    pass


class DeliveryUnavailable(RunnerError):
    pass


def load_suite(exercise: str, variant: str) -> dict[str, Any]:
    rows = json.loads((SUITES / "catalog.json").read_bytes())
    for suite in rows:
        if suite["exerciseId"] == exercise and suite["variantId"] == variant:
            return cast(dict[str, Any], suite)
    raise RunnerError("Unknown exercise or variant in this runner release")


def fingerprint(suite: dict[str, Any], source: bytes) -> str:
    data = {key: value for key, value in suite.items()
            if key != "digest" and (key != "source" or value != "m0.py")}
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(source.replace(b"\r\n", b"\n") + b"\0" + canonical).hexdigest()


def request(api: str, token: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    url = urlsplit(api)
    if (url.scheme != "http" or url.hostname != "127.0.0.1" or url.netloc != f"127.0.0.1:{url.port}"
            or url.path not in ("", "/") or url.query or url.fragment or not url.port):
        raise RunnerError("Use the loopback Quest API URL, including its port")
    connection = http.client.HTTPConnection("127.0.0.1", url.port, timeout=8)
    try:
        connection.request("POST", f"/api/v1{path}", json.dumps(body), {
            "Content-Type": "application/json", "Authorization": f"Bearer {token}",
        })
        response = connection.getresponse()
        if response.status in {502, 503, 504}:
            raise DeliveryUnavailable(f"API temporarily unavailable ({response.status})")
        raw = response.read(32769)
    finally:
        connection.close()
    if len(raw) > 32768:
        raise RunnerError("API returned an oversized response")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise RunnerError("API response is not JSON") from None
    if not isinstance(payload, dict):
        raise RunnerError("Unexpected API response")
    if response.status >= 300:
        code = payload.get("code")
        raise RunnerError(f"API rejected request ({response.status}, {code})")
    return payload


def read_cases(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or path.stat().st_size > 2_000_000:
        return []
    raw = path.read_bytes()
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    results: dict[str, str] = {}
    statuses = ("error", "failure", "skipped")
    for case in root.iter("testcase"):
        name = case.get("name")
        if not name or len(name) > 64 or len(results) >= 30:
            return []
        status = next((key for key in statuses if case.find(key) is not None), "passed")
        if name in results:
            return []
        results[name] = "failed" if status == "failure" else status
    return [{"id": name, "status": status} for name, status in results.items()]


def run_suite(suite: dict[str, Any], workspace: Path, timeout: int) -> tuple[int, list[dict[str, str]], int]:
    workspace = workspace.resolve()
    student = (workspace / suite["starter"]).resolve()
    if student.parent != workspace or not student.is_file() or student.stat().st_size > 512_000:
        raise RunnerError(f"Put {suite['starter']} in the workspace (max 512 KB)")
    filename = suite.get("source", "m0.py")
    if filename not in {"m0.py", "m1.py", "m2.py"}:
        raise RunnerError("Unsupported suite source")
    source = (SUITES / filename).read_bytes()
    if fingerprint(suite, source) != suite["digest"]:
        raise RunnerError("Local suite digest mismatch; reinstall this runner release")
    with tempfile.TemporaryDirectory(prefix="quest-run-") as tmp:
        folder = Path(tmp)
        (folder / "test_quest.py").write_bytes(source)
        (folder / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        target = folder / student.name
        target.write_bytes(student.read_bytes())
        results = folder / "results.xml"
        env = {name: os.environ[name] for name in ("SystemRoot", "WINDIR", "PATH")
               if name in os.environ}
        env.update({
            "HOME": tmp, "USERPROFILE": tmp, "TEMP": tmp, "TMP": tmp, "TMPDIR": tmp,
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "QUEST_EXERCISE": suite["exerciseId"], "QUEST_VARIANT": suite["variantId"],
            "QUEST_STUDENT_FILE": str(target),
        })
        ts = time.monotonic()
        try:
            result = subprocess.run(
                [sys.executable, "-I", "-m", "pytest", "-c", "pytest.ini", "--noconftest",
                 "--junitxml", "results.xml", "test_quest.py"],
                cwd=folder, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=timeout, check=False,
            )
            code = result.returncode if -255 <= result.returncode <= 255 else 1
        except subprocess.TimeoutExpired:
            code = 124
        elapsed = round((time.monotonic() - ts) * 1000)
        return code, read_cases(results) if code != 124 else [], elapsed


def publish(api: str, token: str, report: dict[str, Any]) -> int:
    result = request(api, token, "/runner/reports", report)
    print(f"{report['exerciseId']} / {report['variantId']}: {result['verdict']}")
    for case in report["cases"]:
        print(f"  {case['id']}: {case['status']}")
    return 0 if result["verdict"] == "test_verified_local" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Quest public tests locally")
    commands = parser.add_subparsers(dest="command", required=True)
    test = commands.add_parser("test", help="run an exercise and submit its report")
    test.add_argument("--exercise", required=True)
    test.add_argument("--variant", default="v1")
    test.add_argument("--workspace", required=True, type=Path)
    test.add_argument("--timeout", type=int, default=30, choices=range(1, 121), metavar="1..120")
    test.add_argument("--challenge", type=UUID)
    test.add_argument("--report-dir", default=Path(".quest-reports"), type=Path)
    submit = commands.add_parser("submit", help="retry sending a saved report")
    submit.add_argument("--report", required=True, type=Path)
    for command in (test, submit):
        command.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    token = os.getenv("QUEST_RUNNER_TOKEN")
    if not token:
        parser.error("Set QUEST_RUNNER_TOKEN using Quest Settings")
    try:
        if args.command == "submit":
            if args.report.stat().st_size > 32768:
                raise RunnerError("Report file is too large")
            report = json.loads(args.report.read_bytes())
            if not isinstance(report, dict):
                raise RunnerError("Expected a report object")
            return publish(args.api, token, report)
        suite = load_suite(args.exercise, args.variant)
        exercise_path = f"/exercises/{args.exercise}/challenges"
        challenge = str(args.challenge) if args.challenge else request(
            args.api, token, exercise_path, {"variantId": args.variant},
        )["challengeId"]
        started = datetime.now(UTC).isoformat()
        code, cases, elapsed = run_suite(suite, args.workspace, args.timeout)
        report = {
            "schemaVersion": 1, "challengeId": challenge, "reportId": str(uuid4()),
            "exerciseId": args.exercise, "variantId": args.variant,
            "contentVersion": suite["contentVersion"], "suiteId": suite["id"],
            "suiteDigest": suite["digest"], "startedAt": started, "durationMs": elapsed,
            "exitCode": code, "expectedIds": suite["testIds"], "cases": cases,
            "runnerVersion": VERSION,
        }
        try:
            return publish(args.api, token, report)
        except (OSError, http.client.HTTPException, DeliveryUnavailable):
            args.report_dir.mkdir(parents=True, exist_ok=True)
            path = args.report_dir / f"{report['reportId']}.json"
            with path.open("x", encoding="utf-8") as file:
                json.dump(report, file)
            print(f"Report saved | quest-runner submit --report \"{path}\"", file=sys.stderr)
            return 2
    except (OSError, ValueError, KeyError, http.client.HTTPException, RunnerError) as exc:
        message = str(exc) if isinstance(exc, RunnerError) else type(exc).__name__
        print(f"Quest Runner: {message}", file=sys.stderr)
        return 2
