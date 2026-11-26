from collections.abc import Mapping
from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any

from sqlalchemy import select, update

from app.api.input import RunnerReport
from app.db.models import Challenge, Evidence, Report, RunnerToken
from app.domain.content import Exercise, Pack
from app.domain.engine import Learning, Problem, now


def active_token(learning: Learning) -> RunnerToken | None:
    return learning.db.scalars(select(RunnerToken).where(
        RunnerToken.learner_id == learning.learner.id, RunnerToken.revoked_at.is_(None)
    )).first()


def rotate_token(learning: Learning, create: bool) -> str | None:
    db, learner = learning.db, learning.learner
    db.execute(update(RunnerToken).where(
        RunnerToken.learner_id == learner.id, RunnerToken.revoked_at.is_(None)
    ).values(revoked_at=now()))
    learning.bump()
    if not create:
        return None
    token = token_urlsafe(32)
    digest = sha256(token.encode()).hexdigest()
    db.add(RunnerToken(digest=digest, learner_id=learner.id, created_at=now()))
    return token


def authenticate(learning: Learning, authorization: str | None) -> RunnerToken:
    value = authorization.removeprefix("Bearer ") if authorization else ""
    if not authorization or not authorization.startswith("Bearer ") or len(value) != 43:
        raise Problem(401, "runner_unauthorized")
    token = learning.db.get(RunnerToken, sha256(value.encode()).hexdigest())
    if not token or token.revoked_at or token.learner_id != learning.learner.id:
        raise Problem(401, "runner_unauthorized")
    return token


def issue(learning: Learning, exercise: Exercise, variant: str,
          token: RunnerToken) -> dict[str, Any]:
    suite = learning.content.suites.get((exercise.id, variant))
    if suite is None:
        raise Problem(404, "not_found")
    expires = now() + timedelta(hours=24)
    row = Challenge(learner_id=learning.learner.id, token_digest=token.digest,
                    exercise_id=exercise.id, variant=variant, version=suite.contentVersion,
                    suite_id=suite.id, suite_digest=suite.digest, expires_at=expires)
    learning.db.add(row)
    learning.bump()
    learning.db.flush()
    return {
        "challengeId": str(row.id), "expiresAt": expires.isoformat(),
        "suite": suite.model_dump(), "revision": learning.learner.revision,
    }


def ingest(learning: Learning, token: RunnerToken, report: RunnerReport) -> dict[str, Any]:
    db = learning.db
    challenge = db.get(Challenge, report.challengeId)
    if not challenge or (challenge.learner_id, challenge.token_digest) != (
        learning.learner.id, token.digest
    ):
        raise Problem(404, "not_found")
    payload = report.model_dump(mode="json")
    previous = db.get(Report, report.reportId)
    if previous:
        if previous.challenge_id != challenge.id or previous.payload != payload:
            raise Problem(409, "report_conflict")
        evidence = db.get(Evidence, report.reportId)
        assert evidence
        return response(learning, evidence)
    if challenge.consumed_at:
        raise Problem(409, "challenge_consumed")
    if challenge.expires_at <= now():
        raise Problem(409, "challenge_expired")
    pack_and_exercise = learning.content.exercises.get(report.exerciseId)
    suite = learning.content.suites.get((report.exerciseId, report.variantId))
    if (not pack_and_exercise or not suite
            or (report.exerciseId, report.variantId, report.contentVersion, report.suiteId,
                report.suiteDigest) != (
                    challenge.exercise_id, challenge.variant, challenge.version,
                    challenge.suite_id, challenge.suite_digest
                )
            or (suite.id, suite.digest) != (challenge.suite_id, challenge.suite_digest)
            or report.expectedIds != suite.testIds):
        raise Problem(409, "suite_mismatch")
    actual = {case.id: case.status for case in report.cases}
    if len(actual) != len(report.cases) or set(actual) - set(suite.testIds):
        raise Problem(422, "invalid_cases")
    if db.get(Evidence, report.reportId):
        raise Problem(409, "report_conflict")
    pack, exercise = pack_and_exercise
    evidence = derive_evidence(learning, pack, exercise, report, actual, suite.testIds)
    challenge.consumed_at = now()
    db.add(evidence)
    db.flush()
    db.add(Report(id=report.reportId, challenge_id=report.challengeId, payload=payload))
    if evidence.verdict == "failed" and learning.mastered(pack.id):
        learning.row(pack).review_due = True
    learning.bump()
    learning.recompute()
    return response(learning, evidence)


def derive_evidence(
    learning: Learning, pack: Pack, exercise: Exercise, report: RunnerReport,
    actual: Mapping[str, str], expected: list[str],
) -> Evidence:
    complete = actual.keys() == set(expected)
    passed = report.exitCode == 0 and complete and all(s == "passed" for s in actual.values())
    diagnostic = (exercise.diagnostic and report.exitCode == 1 and complete
                  and all(s in ("passed", "failed") for s in actual.values())
                  and "failed" in actual.values())
    guidance = learning.guidance(pack, exercise, report.variantId)
    guided = bool(guidance and guidance.revealed_at)
    verdict = "failed"
    if passed or diagnostic:
        verdict = ("guided" if guided else
                   "test_verified_local" if passed else "diagnostic_recorded")
    return Evidence(
        id=report.reportId, learner_id=learning.learner.id, exercise_id=exercise.id,
        variant=report.variantId, version=pack.contentVersion, verdict=verdict,
        accepted=(passed or diagnostic) and not guided, created_at=now(),
    )


def response(learning: Learning, evidence: Evidence) -> dict[str, Any]:
    return {
        "reportId": str(evidence.id), "verdict": evidence.verdict,
        "accepted": evidence.accepted, "revision": learning.learner.revision,
    }
