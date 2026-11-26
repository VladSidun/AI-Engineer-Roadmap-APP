from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from os import environ
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sqlalchemy import URL, Engine, create_engine, text
from sqlalchemy.orm import Session

from app.config import ROOT, Config
from app.db.models import Challenge
from app.domain.content import Content
from app.main import create_app

pytestmark = pytest.mark.integration
BASE = "http://127.0.0.1:8311"
ORIGIN = {"Origin": BASE}
API = "/api/v1"
EXERCISE = "/exercises/W01-L03-E1"
REPORTS = "/runner/reports"


@pytest.fixture(scope="module")
def isolated_engine() -> Iterator[Engine]:
    secret = environ.get("QUEST_TEST_DB_PASSWORD")
    port = environ.get("QUEST_TEST_DB_PORT")
    if not secret or not port:
        pytest.skip("Set QUEST_TEST_DB_PORT and QUEST_TEST_DB_PASSWORD for the PostgreSQL fixture")
    database = f"quest_test_{uuid4().hex}"
    url = URL.create("postgresql+psycopg", username="quest", password=secret, host="127.0.0.1",
                     port=int(port), database="postgres")
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    engine = create_engine(url.set(database=database))
    try:
        config = AlembicConfig(ROOT / "backend/alembic.ini")
        # The migration env can use the same connection that the test owns.
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            command.upgrade(config, "head")
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0003"
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{database}"'))
        admin.dispose()


@pytest.fixture()
def client(isolated_engine: Engine) -> Iterator[TestClient]:
    with isolated_engine.begin() as connection:
        connection.execute(text("TRUNCATE learner CASCADE"))
    with TestClient(create_app(Config(port=8311), isolated_engine), base_url=BASE) as session:
        yield session


@pytest.fixture()
def token(client: TestClient) -> dict[str, str]:
    response = client.post(API + "/settings/runner-token", headers=ORIGIN)
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


def new_report(client, token, exercise=EXERCISE, variant="v1"):
    issued = client.post(API + exercise + "/challenges", headers=token, json={"variantId": variant})
    assert issued.status_code == 200, issued.text
    order = issued.json()
    suite = order["suite"]
    return {
        "schemaVersion": 1, "reportId": str(uuid4()), "challengeId": order["challengeId"],
        "exerciseId": suite["exerciseId"], "variantId": suite["variantId"], "contentVersion": suite["contentVersion"],
        "suiteId": suite["id"], "suiteDigest": suite["digest"], "startedAt": datetime.now(UTC).isoformat(),
        "durationMs": 10, "exitCode": 0, "expectedIds": suite["testIds"],
        "cases": [{"id": key, "status": "passed"} for key in suite["testIds"]], "runnerVersion": "1.0.0",
    }


def test_readiness_locale_and_restart(client, isolated_engine):
    assert client.get("/health").json()["status"] == "ready"
    key = API + "/lessons/W01-L01"
    left = client.get(key).json()
    assert left["title"] != client.get(key + "?locale=en").json()["title"]
    assert {"correct", "explanation"}.isdisjoint(left["questions"][0]["options"][0])
    assert left["exercises"][0]["variants"][0]["solution"] is None
    assert client.put(API + "/settings", headers=ORIGIN, json={"locale": "en"}).status_code == 200
    first = client.post(key + "/read", headers=ORIGIN).json()
    assert client.post(key + "/read", headers=ORIGIN).json() == first
    with TestClient(create_app(Config(port=8311), isolated_engine), base_url=BASE) as restarted:
        assert restarted.get(API + "/settings").json()["locale"] == "en"
        assert restarted.get(API + "/progress").json()["items"]["W01-L01"]["read"]


def test_defensive_request_boundaries(client, token):
    path = API + "/settings"
    assert client.get("/health", headers={"Host": "localhost:8311"}).status_code == 403
    for headers in ({}, {"Origin": "null"}, {"Origin": BASE + ".invalid"}, {"Origin": "http://127.0.0.1:5173"}):
        assert client.put(path, headers=headers, json={"locale": "en"}).status_code == 403
    assert client.get(path, headers=token).json()["code"] == "runner_scope"
    assert client.put(path, headers=ORIGIN, content=b" " * 32769).status_code == 413
    assert client.put(path, headers=ORIGIN, json={"locale": "ua"}).status_code == 422
    assert client.get("/health").headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in client.get("/health").headers["Content-Security-Policy"]


def test_exact_development_origin(isolated_engine):
    with TestClient(create_app(Config(port=8311, dev=True), isolated_engine), base_url=BASE) as client:
        settings = API + "/settings"
        assert client.put(settings, headers={"Origin": "http://127.0.0.1:5173"}, json={"locale": "en"}).status_code == 200
        assert client.put(settings, headers={"Origin": "http://127.0.0.1:5174"}, json={"locale": "en"}).status_code == 403


def test_viewport_clamps_and_persists_separate_camera_and_stage(client, token, isolated_engine):
    path = API + "/viewport/main"
    initial = client.get(path).json()
    assert initial == {"camera": None, "lastStageId": None, "lastActivityId": None}
    assert client.put(path, headers=token, json={"lastStageId": "W01"}).status_code == 403
    assert client.put(path, headers=ORIGIN, json={"lastStageId": "G-M0"}).status_code == 422
    assert client.put(path, headers=ORIGIN, json={"lastStageId": "W07"}).json()["lastStageId"] == "W07"
    camera = {"x": -20, "y": 9000, "zoom": 7, "selection": "W07"}
    assert client.put(path, headers=ORIGIN, json={"camera": {**camera, "selection": "W99"}}).status_code == 422
    saved = client.put(path, headers=ORIGIN, json={"camera": camera}).json()
    layout = client.get(API + "/campaigns/main/map").json()["layout"]
    assert saved == {"camera": {"x": 0, "y": layout["worldHeight"], "zoom": 2, "selection": "W07"},
                     "lastStageId": "W07", "lastActivityId": None}
    assert client.put(path, headers=ORIGIN, json={"camera": camera}).json() == saved
    with TestClient(create_app(Config(port=8311), isolated_engine), base_url=BASE) as restarted:
        assert restarted.get(path).json() == saved


def test_published_activity_persists_independently_of_map_browsing(client, isolated_engine):
    path = API + "/viewport/main"
    assert client.put(path, headers=ORIGIN, json={"lastActivityId": "W07-L01"}).status_code == 422
    assert client.put(path, headers=ORIGIN, json={"lastActivityId": "W02-L01", "lastStageId": "W01"}).status_code == 422
    activity = client.put(path, headers=ORIGIN, json={"lastActivityId": "W02-L01"}).json()
    assert activity == {"camera": None, "lastStageId": "W02", "lastActivityId": "W02-L01"}
    saved = client.put(path, headers=ORIGIN, json={
        "camera": {"x": 530, "y": 1290, "zoom": 1, "selection": "M9"}, "lastStageId": "W20",
    }).json()
    assert saved["lastActivityId"] == "W02-L01" and saved["lastStageId"] == "W20"
    with TestClient(create_app(Config(port=8311), isolated_engine), base_url=BASE) as restarted:
        assert restarted.get(path).json() == saved
        lesson = restarted.get(API + "/lessons/W02-L01?locale=en").json()
        assert lesson["module"]["title"] == "Professional Python"
        assert lesson["stage"]["title"] == "Maintainable Python"
        assert lesson["prerequisiteEntries"][0]["id"] == "G-M0"


def test_early_evidence_promotes_across_modules_and_project_rewards_are_unique(client, token):
    content = Content()

    def quiz(key):
        pack = content.packs[key]
        submission = {"submissionId": str(uuid4()),
                      "answers": {question.id: question.correct for question in pack.questions}}
        response = client.post(f"{API}/assessments/{key}/attempts", headers=ORIGIN, json=submission)
        assert response.status_code == 200 and response.json()["attempt"]["passed"]
        return submission

    def complete(key, *, take_quiz=True):
        if key in content.lessons:
            assert client.post(f"{API}/lessons/{key}/read", headers=ORIGIN).status_code == 200
        if take_quiz:
            quiz(key)
        for exercise in content.packs[key].exercises:
            path = f"/exercises/{exercise.id}"
            if exercise.kind == "code":
                report = new_report(client, token, exercise=path)
                response = client.post(API + REPORTS, headers=token, json=report)
                assert response.status_code == 200 and response.json()["verdict"] == "test_verified_local"
                assert response.json() == client.post(API + REPORTS, headers=token, json=report).json()
            else:
                attestation = {"submissionId": str(uuid4()), "variantId": "v1",
                               "criteria": [criterion.id for criterion in exercise.criteria],
                               "note": "Synthetic rubric evidence from a disposable integration fixture."}
                response = client.post(API + path + "/manual-evidence", headers=ORIGIN, json=attestation)
                assert response.status_code == 200 and response.json()["attempt"]["accepted"]

    future = "W02-L01"
    assert client.get(f"{API}/lessons/{future}?locale=en").status_code == 200
    early_quiz = quiz(future)
    progress = client.get(API + "/progress").json()
    assert progress["items"][future]["provisionalEvidence"]
    assert progress["items"][future]["missing"] == ["G-M0"]
    assert progress["items"][future]["state"] == "in_progress"
    assert progress["xp"] == 0

    complete("W02-L02")
    complete(future, take_quiz=False)
    complete("SR-W02")
    complete("G-M1")
    complete("SR-W04")
    complete("W04-L01")
    project_path = API + "/projects/A"
    early_milestones = client.get(project_path).json()["milestones"]
    assert [milestone["stageId"] for milestone in early_milestones] == ["W04", "W05", "W06"]
    assert early_milestones[0]["evidence"]["state"] == "pending_prerequisites"
    assert client.get(project_path + "?locale=uk").json()["title"] != client.get(project_path + "?locale=en").json()["title"]
    state = client.get(API + "/progress").json()
    assert all(state["items"][key]["state"] == "pending_prerequisites"
               for key in (future, "W02-L02", "SR-W02", "G-M1"))
    assert state["xp"] == 0
    for key in ("W01-L01", "W01-L02", "W01-L03", "W01-L04", "SR-W01", "G-M0"):
        complete(key)
    state = client.get(API + "/progress").json()
    assert state["xp"] == 1050
    assert state["items"][future]["state"] == state["items"]["W02-L02"]["state"] == "mastered"
    assert not state["items"][future]["provisionalEvidence"]
    assert state["items"]["SR-W02"]["state"] == "pending_prerequisites"
    assert client.post(f"{API}/assessments/{future}/attempts", headers=ORIGIN, json=early_quiz).status_code == 200
    assert client.post(f"{API}/lessons/{future}/read", headers=ORIGIN).status_code == 200
    assert client.get(API + "/progress").json()["xp"] == 1050

    for key in ("W02-L03", "W02-L04", "W03-L01", "W03-L02", "W03-L03", "W03-L04", "SR-W03"):
        complete(key)
    state = client.get(API + "/progress").json()
    assert all(state["items"][key]["state"] == "mastered" for key in ("SR-W02", "SR-W03", "G-M1"))
    assert state["xp"] == 2350  # M0 and M1 plus the promoted W04-L01.
    assert state["items"]["W04-L01"]["state"] == "mastered"

    for key in ("W04-L02", "W04-L03", "W04-L04"):
        complete(key)
    first_milestone = client.get(project_path).json()["milestones"][0]
    assert first_milestone["evidence"]["state"] == "mastered"
    assert first_milestone["evidence"]["practices"]["SR-W04-E1"]["history"][0]["verdict"] == "self_assessed"
    assert client.get(API + "/progress").json()["xp"] == 2900
    quiz("SR-W04")
    assert client.get(API + "/progress").json()["xp"] == 2900

    for stage in ("W05", "W06"):
        for number in range(1, 5):
            complete(f"{stage}-L{number:02}")
        complete(f"SR-{stage}")
    complete("G-M2")
    assert client.get(API + "/progress").json()["xp"] == 4500
    assert all(milestone["evidence"]["state"] == "mastered"
               for milestone in client.get(project_path).json()["milestones"])


def test_server_grading_and_concurrent_replay(client):
    content = Content().packs["W01-L01"]
    answers = {question.id: question.correct for question in content.questions}
    path = API + "/assessments/W01-L01/attempts"
    body = {"submissionId": str(uuid4()), "answers": answers}
    assert client.post(path, headers=ORIGIN, json={**body, "score": 100}).status_code == 422
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(path, headers=ORIGIN, json=body), range(2)))
    assert all(response.status_code == 200 for response in responses)
    one, two = [response.json() for response in responses]
    assert one["attempt"] == two["attempt"] and one["revision"] == two["revision"]
    assert one["attempt"]["correct"] == len(content.questions)
    wrong = {question.id: [next(option.id for option in question.options if option.id not in question.correct)]
             for question in content.questions}
    assert client.post(path, headers=ORIGIN, json={**body, "answers": wrong}).status_code == 409
    failed = client.post(path, headers=ORIGIN, json={"submissionId": str(uuid4()), "answers": wrong}).json()
    assert failed["attempt"]["correct"] == 0
    result = path + "/" + failed["attempt"]["id"]
    assert client.get(result + "?locale=en").json()["feedback"] != client.get(result + "?locale=uk").json()["feedback"]


@pytest.mark.parametrize("mode", ["fail", "timeout", "skip", "zero", "missing", "error"])
def test_failed_reports_do_not_award_practice(client, token, mode):
    report = new_report(client, token)
    if mode == "fail":
        report["exitCode"] = 1
        report["cases"][0]["status"] = "failed"
    elif mode == "timeout":
        report.update(exitCode=124, cases=[])
    elif mode in {"skip", "error"}:
        report["cases"][0]["status"] = "skipped" if mode == "skip" else "error"
    elif mode == "zero":
        report["cases"] = []
    else:
        report["cases"].pop()
    received = client.post(API + REPORTS, headers=token, json=report)
    assert received.status_code == 200
    assert received.json()["verdict"] == "failed" and not received.json()["accepted"]
    assert client.get(API + EXERCISE + "/attempts").json()["accepted"] is False


def test_reports_validate_and_replay_safely(client, token, isolated_engine):
    report = new_report(client, token)
    path = API + REPORTS
    assert client.post(path, json=report).status_code == 401
    for field, value in [("suiteDigest", "a" * 64), ("variantId", "v2"), ("suiteId", "other"), ("contentVersion", 2)]:
        assert client.post(path, headers=token, json={**report, field: value}).json()["code"] == "suite_mismatch"
    assert client.post(path, headers=token, json={**report, "passed": True}).status_code == 422
    invalid = report["cases"] + [report["cases"][0]]
    assert client.post(path, headers=token, json={**report, "cases": invalid}).json()["code"] == "invalid_cases"
    unexpected = [{"id": "wrong_case", "status": "passed"}]
    assert client.post(path, headers=token, json={**report, "cases": unexpected}).json()["code"] == "invalid_cases"
    approved = client.post(path, headers=token, json=report)
    assert approved.status_code == 200 and approved.json()["verdict"] == "test_verified_local"
    assert client.post(path, headers=token, json=report).json() == approved.json()
    assert client.post(path, headers=token, json={**report, "exitCode": 1}).json()["code"] == "report_conflict"
    assert client.post(path, headers=token, json={**report, "reportId": str(uuid4())}).json()["code"] == "challenge_consumed"
    expired = new_report(client, token)
    with Session(isolated_engine) as db, db.begin():
        db.get(Challenge, UUID(expired["challengeId"])).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert client.post(path, headers=token, json=expired).json()["code"] == "challenge_expired"
    assert client.delete(API + "/settings/runner-token", headers=ORIGIN).status_code == 200
    assert client.post(path, headers=token, json=report).status_code == 401


def test_guidance_and_diagnostic_exception(client, token):
    assert client.post(API + EXERCISE + "/hints/2", headers=ORIGIN, json={}).status_code == 409
    assert client.post(API + EXERCISE + "/hints/1", headers=ORIGIN, json={}).status_code == 200
    for variant, status in [("v1", 200), ("v2", 200), ("v3", 409)]:
        assert client.post(API + EXERCISE + "/reveal", headers=ORIGIN, json={"variantId": variant}).status_code == status
    assert client.post(API + REPORTS, headers=token, json=new_report(client, token)).json()["verdict"] == "guided"
    assert client.post(API + REPORTS, headers=token, json=new_report(client, token, variant="v3")).json()["accepted"]
    diagnostic = new_report(client, token, "/exercises/W01-L04-E1")
    diagnostic["cases"][0]["status"] = "failed"
    diagnostic["exitCode"] = 1
    result = client.post(API + REPORTS, headers=token, json=diagnostic).json()
    assert result["verdict"] == "diagnostic_recorded" and result["accepted"]
    assert client.get(API + "/progress").json()["items"]["W01-L04"]["missing"] == ["W01-L03"]
    assert client.post(API + EXERCISE + "/manual-evidence", headers=ORIGIN, json={
        "criteria": ["anything"], "note": "This cannot satisfy a required code practice.", "submissionId": str(uuid4()),
    }).json()["code"] == "code_requires_runner"
