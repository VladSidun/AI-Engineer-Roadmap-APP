from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assessment, Evidence, Guidance, Learner, Progress, Reward
from app.domain.content import Content, Exercise, Pack


class Problem(Exception):
    def __init__(self, status: int, code: str):
        self.status = status
        self.code = code


def now() -> datetime:
    return datetime.now(UTC)


class Learning:
    def __init__(self, db: Session, content: Content, learner: Learner):
        self.db = db
        self.content = content
        self.learner = learner
        self.progress = {
            p.content_id: p for p in db.scalars(select(Progress).where(
                Progress.learner_id == learner.id
            )) if p.content_id in content.packs
            and p.version == content.packs[p.content_id].contentVersion
        }

    def bump(self) -> None:
        self.learner.revision += 1

    def row(self, pack: Pack) -> Progress:
        row = self.progress.get(pack.id)
        if row is None:
            row = Progress(learner_id=self.learner.id, content_id=pack.id,
                           version=pack.contentVersion, review_due=False)
            self.db.add(row)
            self.progress[pack.id] = row
        return row

    def guidance(self, pack: Pack, exercise: Exercise, variant: str) -> Guidance | None:
        return self.db.get(Guidance, (self.learner.id, exercise.id, variant, pack.contentVersion))

    def attempts(self, exercise: Exercise, version: int) -> list[Evidence]:
        return list(self.db.scalars(select(Evidence).where(
            Evidence.learner_id == self.learner.id, Evidence.exercise_id == exercise.id,
            Evidence.version == version,
        ).order_by(Evidence.created_at.desc(), Evidence.id.desc())))

    def recompute(self) -> None:
        passed_quizzes = {
            (row.assessment_id, row.version)
            for row in self.db.scalars(select(Assessment).where(
                Assessment.learner_id == self.learner.id, Assessment.passed
            ))
        }
        accepted = {
            (row.exercise_id, row.version) for row in self.db.scalars(select(Evidence).where(
                Evidence.learner_id == self.learner.id, Evidence.accepted
            ))
        }
        for key in self.content.order:
            pack = self.content.packs.get(key)
            if pack is None or self.mastered(key) or self.missing(key):
                continue
            if (key, pack.contentVersion) not in passed_quizzes:
                continue
            if any((e.id, pack.contentVersion) not in accepted for e in pack.exercises):
                continue
            if key in self.content.lessons and (
                key not in self.progress or self.progress[key].read_at is None
            ):
                continue
            self.row(pack).mastered_at = now()
            amounts = 100 if key in self.content.lessons else 150 if key in self.content.reviews else 300
            self.reward(key, amounts)
        for project in self.content.projects.values():
            for milestone in project.milestones:
                if self.mastered(milestone.evidenceId):
                    self.reward(f"project:{milestone.id}", 100)

    def reward(self, key: str, amount: int) -> None:
        if self.db.get(Reward, (self.learner.id, key)) is None:
            self.db.add(Reward(learner_id=self.learner.id, event_key=key,
                               amount=amount, created_at=now()))

    def mastered(self, key: str) -> bool:
        return key in self.progress and self.progress[key].mastered_at is not None

    def missing(self, key: str) -> list[str]:
        return [parent for parent in self.content.entries[key].prerequisites
                if not self.mastered(parent)]

    def result(self, key: str) -> dict[str, Any]:
        pack = self.content.packs[key]
        row = self.progress.get(key)
        read = bool(row and row.read_at)
        mastered = self.mastered(key)
        missing = self.missing(key)
        attempts = list(self.db.scalars(select(Assessment).where(
            Assessment.learner_id == self.learner.id, Assessment.assessment_id == key,
            Assessment.version == pack.contentVersion,
        ).order_by(Assessment.created_at.desc(), Assessment.id.desc())))
        quiz = attempts[0] if attempts else None
        ever_passed = any(attempt.passed for attempt in attempts)
        practices: dict[str, Any] = {}
        for exercise in pack.exercises:
            history = self.attempts(exercise, pack.contentVersion)
            practices[exercise.id] = {
                "accepted": any(attempt.accepted for attempt in history),
                "history": [evidence_view(attempt) for attempt in history[:10]],
                "guidance": {v.id: guidance_view(self.guidance(pack, exercise, v.id))
                             for v in exercise.variants},
            }
        all_tasks = all(p["accepted"] for p in practices.values())
        ready = all_tasks and ever_passed and (read or key not in self.content.lessons)
        started = read or bool(quiz) or any(
            p["history"] or any(g["hints"] or g["revealed"] for g in p["guidance"].values())
            for p in practices.values()
        )
        state = "available"
        if mastered:
            state = "mastered"
        elif ready and missing:
            state = "pending_prerequisites"
        elif started:
            state = "in_progress"
        return {
            "id": key, "state": state, "read": read, "missing": missing,
            "reviewDue": bool(row and row.review_due), "quizPassed": ever_passed,
            "provisionalEvidence": bool(missing and (ever_passed or any(
                practice["accepted"] for practice in practices.values()
            ))),
            "latestQuiz": assessment_view(quiz) if quiz else None,
            "practices": practices,
        }

    def state(self) -> dict[str, Any]:
        rows = self.db.scalars(select(Reward).where(Reward.learner_id == self.learner.id))
        xp = sum(row.amount for row in rows)
        return {
            "locale": self.learner.locale, "revision": self.learner.revision,
            "xp": xp, "level": 1 + xp // 500,
            "items": {key: self.result(key) for key in self.content.packs},
        }


def guidance_view(row: Guidance | None) -> dict[str, int | bool]:
    return {"hints": row.hints if row else 0, "revealed": bool(row and row.revealed_at)}


def assessment_view(attempt: Assessment) -> dict[str, int | bool | str]:
    return {"correct": attempt.correct, "total": attempt.total, "passed": attempt.passed,
            "id": str(attempt.id), "createdAt": attempt.created_at.isoformat()}


def evidence_view(attempt: Evidence) -> dict[str, bool | str]:
    return {
        "id": str(attempt.id), "variantId": attempt.variant, "verdict": attempt.verdict,
        "accepted": attempt.accepted, "createdAt": attempt.created_at.isoformat(),
    }


def existing_assessment(
    db: Session, submission_id: UUID, pack: Pack, answers: dict[str, list[str]],
) -> Assessment | None:
    prior = db.get(Assessment, submission_id)
    if prior and (prior.assessment_id, prior.version, prior.answers) != (
        pack.id, pack.contentVersion, answers
    ):
        raise Problem(409, "submission_conflict")
    return prior
