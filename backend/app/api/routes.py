from collections.abc import Iterator
from random import SystemRandom
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import runner
from app.api.input import (
    Preferences,
    QuizAnswers,
    Rubric,
    RunnerReport,
    VariantRequest,
    ViewportInput,
)
from app.db.models import Assessment, Evidence, Guidance, Learner, Viewport
from app.db.session import learner_for_update
from app.domain.content import Entry, Exercise, Gate, Locale, Pack, StageItem, Variant
from app.domain.engine import Learning, Problem, assessment_view, evidence_view, existing_assessment
from app.domain.engine import now as utc_now
from app.domain.grading import grade, passes

api = APIRouter(prefix="/api/v1")
random = SystemRandom()


def learn(request: Request) -> Iterator[Learning]:
    engine = request.app.state.engine
    with Session(engine) as db, db.begin():
        learner = (learner_for_update(db) if request.method != "GET" else
                   db.scalars(select(Learner).where(Learner.singleton == 1)).one())
        yield Learning(db, request.app.state.content, learner)


Current = Annotated[Learning, Depends(learn, scope="function")]


def local(learning: Learning, locale: Locale | None) -> Locale:
    if locale:
        return locale
    return "en" if learning.learner.locale == "en" else "uk"


def selected(learning: Learning, key: str) -> Pack:
    pack = learning.content.packs.get(key)
    if not pack:
        raise Problem(404, "not_found")
    return pack


def task(learning: Learning, key: str, variant_id: str) -> tuple[Pack, Exercise, Variant]:
    row = learning.content.exercises.get(key)
    if row:
        pack, exercise = row
        for variant in exercise.variants:
            if variant.id == variant_id:
                return pack, exercise, variant
    raise Problem(404, "not_found")


def title(entry: Entry, locale: Locale) -> dict[str, Any]:
    return {"id": entry.id, "title": entry.title.get(locale), "availability": entry.availability,
            "estimateMinutes": entry.estimateMinutes, "prerequisites": entry.prerequisites}


def roadmap(learning: Learning, locale: Locale) -> list[dict[str, Any]]:
    c = learning.content
    return [
        {**title(m, locale), "gate": title(c.gates[m.gateId], locale), "stages": [
            {**title(s, locale), "review": title(c.reviews[s.reviewId], locale),
             "lessons": [title(c.lessons[key], locale) for key in s.lessonIds]}
            for s in (c.stages[key] for key in m.stageIds)
        ]} for m in c.modules.values()
    ]


def pack_view(learning: Learning, pack: Pack, locale: Locale) -> dict[str, Any]:
    content = learning.content
    entry = content.entries[pack.id]
    stage = content.stages[entry.stageId] if isinstance(entry, StageItem) else None
    module_id = entry.moduleId if isinstance(entry, Gate) else stage.moduleId if stage else None
    module = content.modules[module_id] if module_id else None
    questions = []
    for q in pack.questions:
        options = [{"id": o.id, "title": o.title.get(locale)} for o in q.options]
        random.shuffle(options)
        questions.append({"id": q.id, "prompt": q.prompt.get(locale), "options": options,
                          "multiple": len(q.correct) > 1})
    exercises = []
    for e in pack.exercises:
        variants = []
        for v in e.variants:
            guide = learning.guidance(pack, e, v.id)
            suite = learning.content.suites.get((e.id, v.id))
            variants.append({
                "id": v.id, "title": v.title.get(locale), "prompt": v.prompt.get(locale),
                "hints": [h.get(locale) for h in v.hints[:guide.hints]] if guide else [],
                "solution": v.solution.get(locale) if guide and guide.revealed_at else None,
                "suite": suite.model_dump() if suite else None,
            })
        exercises.append({
            "id": e.id, "title": e.title.get(locale), "kind": e.kind, "example": e.example.get(locale),
            "estimateMinutes": e.estimateMinutes, "diagnostic": e.diagnostic, "variants": variants,
            "criteria": [{"id": c.id, "title": c.title.get(locale)} for c in e.criteria],
        })
    return {
        **title(entry, locale), "contentVersion": pack.contentVersion,
        "stageId": stage.id if stage else None,
        "stage": title(stage, locale) if stage else None,
        "module": title(module, locale) if module else None,
        "prerequisiteEntries": [title(content.entries[key], locale) for key in entry.prerequisites],
        "overview": pack.overview.get(locale), "theory": pack.theory.get(locale),
        "recap": pack.recap.get(locale), "interview": pack.interview,
        "interviewGuide": pack.interviewGuide.get(locale),
        "objectives": [o.title.get(locale) for o in pack.objectives], "exercises": exercises,
        "sources": [{"title": s.title.get(locale), "url": s.url, "checked": s.checked,
                     "version": s.version} for s in pack.sources], "questions": questions,
        "crosslinks": [title(learning.content.entries[key], locale) for key in pack.crosslinks],
        "examples": [
            {"file": e.file, "code": learning.content.file("examples", e.file).read_text(encoding="utf-8"),
             "expected": e.expected, "explanation": e.explanation.get(locale),
             "error": e.error.get(locale)} for e in pack.examples
        ],
    }


@api.get("/campaigns")
def campaigns(learning: Current, locale: Locale | None = None) -> list[dict[str, str]]:
    return [{"id": c.id, "title": c.title.get(local(learning, locale))} for c in learning.content.manifest.campaigns]


@api.get("/campaigns/{key}/map")
def campaign(key: str, learning: Current, locale: Locale | None = None) -> dict[str, Any]:
    if key != "main":
        raise Problem(404, "not_found")
    return {"id": key, "modules": roadmap(learning, local(learning, locale)),
            "layout": learning.content.layout.model_dump(by_alias=True)}


def viewport_row(key: str, learning: Learning) -> Viewport | None:
    if key != "main":
        raise Problem(404, "not_found")
    return learning.db.get(Viewport, (learning.learner.id, key))


def viewport_view(row: Viewport | None) -> dict[str, Any]:
    camera = None
    if row is not None and row.zoom is not None:
        camera = {"x": row.x, "y": row.y, "zoom": row.zoom, "selection": row.selection}
    return {"camera": camera, "lastStageId": row.last_stage_id if row else None,
            "lastActivityId": row.last_activity_id if row else None}


@api.get("/viewport/{key}")
def viewport(key: str, learning: Current) -> dict[str, Any]:
    return viewport_view(viewport_row(key, learning))


@api.put("/viewport/{key}")
def save_viewport(key: str, body: ViewportInput, learning: Current) -> dict[str, Any]:
    row = viewport_row(key, learning)
    content = learning.content
    if body.lastStageId is not None and body.lastStageId not in content.stages:
        raise Problem(422, "invalid_input")
    activity = content.entries.get(body.lastActivityId) if body.lastActivityId else None
    if body.lastActivityId is not None and (activity is None or activity.availability != "published"):
        raise Problem(422, "invalid_input")
    stage_id = activity.stageId if isinstance(activity, StageItem) else body.lastStageId
    if body.lastStageId is not None and body.lastStageId != stage_id:
        raise Problem(422, "invalid_input")
    camera = body.camera
    if camera is not None and camera.selection not in (
        content.modules.keys() | content.stages.keys() | content.gates.keys()
    ):
        raise Problem(422, "invalid_input")
    if row is None:
        row = Viewport(learner_id=learning.learner.id, campaign_id=key)
        learning.db.add(row)
    if camera is not None:
        row.x = min(content.layout.worldWidth, max(0, camera.x))
        row.y = min(content.layout.worldHeight, max(0, camera.y))
        row.zoom = min(2, max(0.05, camera.zoom))
        row.selection = camera.selection
    if stage_id is not None:
        row.last_stage_id = stage_id
    if activity is not None:
        row.last_activity_id = activity.id
    return viewport_view(row)


@api.get("/regions/{key}")
def region(key: str, learning: Current, locale: Locale | None = None) -> dict[str, Any]:
    for m in roadmap(learning, local(learning, locale)):
        if m["id"] == key:
            return m
    raise Problem(404, "not_found")


@api.get("/stages/{key}")
def stage(key: str, learning: Current, locale: Locale | None = None) -> dict[str, Any]:
    for m in roadmap(learning, local(learning, locale)):
        for s in m["stages"]:
            if s["id"] == key:
                project = next((p.id for p in learning.content.projects.values()
                                if any(x.stageId == key for x in p.milestones)), None)
                return {**s, "moduleId": m["id"], "module": title(learning.content.modules[m["id"]], local(learning, locale)),
                        "projectId": project}
    raise Problem(404, "not_found")


@api.get("/projects/{key}")
def project(key: str, learning: Current, locale: Locale | None = None) -> dict[str, Any]:
    definition = learning.content.projects.get(key)
    if definition is None or definition.availability != "published":
        raise Problem(404, "not_found")
    language = local(learning, locale)
    result = []
    for milestone in definition.milestones:
        evidence = learning.result(milestone.evidenceId)
        result.append({
            "id": milestone.id, "title": milestone.title.get(language),
            "stageId": milestone.stageId, "evidenceId": milestone.evidenceId,
            "stage": title(learning.content.stages[milestone.stageId], language),
            "artifacts": [artifact.get(language) for artifact in milestone.artifacts],
            "evidence": evidence,
        })
    return {"id": key, "title": definition.title.get(language), "milestones": result}


@api.get("/lessons/{key}")
@api.get("/reviews/{key}")
@api.get("/gates/{key}")
def item(key: str, learning: Current, request: Request, locale: Locale | None = None) -> dict[str, Any]:
    route = request.url.path.split("/")[-2]
    known_keys = {"lessons": set(learning.content.lessons),
                  "reviews": set(learning.content.reviews), "gates": set(learning.content.gates)}
    if key not in known_keys[route]:
        raise Problem(404, "not_found")
    language = local(learning, locale)
    gate = learning.content.gates.get(key)
    if gate is not None and gate.availability == "planned":
        module_view = region(gate.moduleId, learning, language)
        return {**title(gate, language), "moduleId": gate.moduleId,
                "module": title(learning.content.modules[gate.moduleId], language),
                "stages": module_view["stages"]}
    return pack_view(learning, selected(learning, key), language)


@api.get("/progress")
def progress(learning: Current) -> dict[str, Any]:
    return learning.state()


@api.get("/settings")
def settings(learning: Current, request: Request) -> dict[str, Any]:
    return {"locale": local(learning, None), "runnerTokenActive": runner.active_token(learning) is not None,
            "runnerApi": f"http://127.0.0.1:{request.app.state.config.port}",
            "revision": learning.learner.revision}


@api.put("/settings")
def preferences(body: Preferences, learning: Current, request: Request) -> dict[str, Any]:
    if learning.learner.locale != body.locale:
        learning.learner.locale = body.locale
        learning.bump()
    return settings(learning, request)


@api.post("/settings/runner-token")
def issue_token(learning: Current, request: Request) -> dict[str, Any]:
    return {"token": runner.rotate_token(learning, True), **settings(learning, request)}


@api.delete("/settings/runner-token")
def revoke_token(learning: Current, request: Request) -> dict[str, Any]:
    if runner.active_token(learning):
        runner.rotate_token(learning, False)
    return settings(learning, request)


@api.post("/lessons/{key}/read")
def mark_read(key: str, learning: Current) -> dict[str, Any]:
    if key not in learning.content.lessons:
        raise Problem(404, "not_found")
    row = learning.row(selected(learning, key))
    if row.read_at is None:
        row.read_at = utc_now()
        learning.bump()
        learning.recompute()
    return {"item": learning.result(key), "revision": learning.learner.revision}


@api.post("/assessments/{key}/attempts")
@api.post("/gates/{key}/attempts")
def assess(key: str, body: QuizAnswers, learning: Current, request: Request,
           locale: Locale | None = None) -> dict[str, Any]:
    if request.url.path.split("/")[-3] == "gates" and key not in learning.content.gates:
        raise Problem(404, "not_found")
    pack = selected(learning, key)
    language = local(learning, locale)
    answers = {key: sorted(value) for key, value in body.answers.items()}
    try:
        correct, results = grade(pack, answers)
    except ValueError:
        raise Problem(422, "invalid_answers") from None
    attempt = existing_assessment(learning.db, body.submissionId, pack, answers)
    if attempt is None:
        count = len(pack.questions)
        passed = passes(correct, count)
        attempt = Assessment(
            id=body.submissionId, learner_id=learning.learner.id, assessment_id=key,
            version=pack.contentVersion, answers=answers, correct=correct, total=count,
            passed=passed, created_at=utc_now(),
        )
        learning.db.add(attempt)
        if not passed and learning.mastered(key):
            learning.row(pack).review_due = True
        learning.bump()
        learning.recompute()
    return {**assessment_feedback(pack, attempt, results, language),
            "item": learning.result(key), "revision": learning.learner.revision}


def assessment_feedback(pack: Pack, attempt: Assessment, results: dict[str, bool],
                        language: Locale) -> dict[str, Any]:
    feedback = [
        {"id": q.id, "correct": results[q.id], "options": [
            {"id": o.id, "correct": o.id in q.correct, "explanation": o.explanation.get(language)}
            for o in q.options
        ]} for q in pack.questions
    ]
    return {"attempt": assessment_view(attempt), "feedback": feedback}


@api.get("/assessments/{key}/attempts/{submission_id}")
def previous_attempt(key: str, submission_id: UUID, learning: Current,
                     locale: Locale | None = None) -> dict[str, Any]:
    pack = selected(learning, key)
    attempt = learning.db.get(Assessment, submission_id)
    if not attempt or (attempt.learner_id, attempt.assessment_id, attempt.version) != (
        learning.learner.id, pack.id, pack.contentVersion
    ):
        raise Problem(404, "not_found")
    _, results = grade(pack, attempt.answers)
    return assessment_feedback(pack, attempt, results, local(learning, locale))


@api.post("/exercises/{key}/manual-evidence")
def attest(key: str, body: Rubric, learning: Current) -> dict[str, Any]:
    pack, ex, variant = task(learning, key, body.variantId)
    if ex.kind != "rubric":
        raise Problem(422, "code_requires_runner")
    criteria = set(body.criteria)
    required = {c.id for c in ex.criteria}
    if criteria - required or len(criteria) != len(body.criteria):
        raise Problem(422, "invalid_criteria")
    saved = learning.db.get(Evidence, body.submissionId)
    values = (key, variant.id, pack.contentVersion, sorted(criteria), body.note)
    if saved and (saved.exercise_id, saved.variant, saved.version, saved.criteria, saved.note) != values:
        raise Problem(409, "submission_conflict")
    if saved is None:
        guide = learning.guidance(pack, ex, variant.id)
        guided = bool(guide and guide.revealed_at)
        passed = criteria == required
        verdict = ("guided" if guided else "self_assessed") if passed else "failed"
        saved = Evidence(id=body.submissionId, learner_id=learning.learner.id, exercise_id=key,
                         variant=variant.id, version=pack.contentVersion, verdict=verdict,
                         accepted=passed and not guided, criteria=sorted(criteria), note=body.note,
                         created_at=utc_now())
        learning.db.add(saved)
        if not passed and learning.mastered(pack.id):
            learning.row(pack).review_due = True
        learning.bump()
        learning.recompute()
    return {"attempt": evidence_view(saved), "item": learning.result(pack.id),
            "revision": learning.learner.revision}


def guide_for(learning: Learning, pack: Pack, ex: Exercise, variant: Variant) -> Guidance:
    guide = learning.guidance(pack, ex, variant.id)
    if guide is None:
        guide = Guidance(learner_id=learning.learner.id, exercise_id=ex.id, variant=variant.id,
                         version=pack.contentVersion, hints=0)
        learning.db.add(guide)
    return guide


@api.post("/exercises/{key}/hints/{index}")
def hint(key: str, index: int, body: VariantRequest, learning: Current,
         locale: Locale | None = None) -> dict[str, Any]:
    pack, ex, variant = task(learning, key, body.variantId)
    guide = guide_for(learning, pack, ex, variant)
    if not 1 <= index <= 3 or index > guide.hints + 1:
        raise Problem(409, "hint_order")
    if index > guide.hints:
        guide.hints = index
        learning.bump()
    return {"hints": [h.get(local(learning, locale)) for h in variant.hints[:guide.hints]],
            "revision": learning.learner.revision}


@api.post("/exercises/{key}/reveal")
def reveal(key: str, body: VariantRequest, learning: Current,
           locale: Locale | None = None) -> dict[str, Any]:
    pack, ex, variant = task(learning, key, body.variantId)
    guide = guide_for(learning, pack, ex, variant)
    if not guide.revealed_at:
        alternatives = [learning.guidance(pack, ex, v.id) for v in ex.variants if v.id != variant.id]
        if (all(g and g.revealed_at for g in alternatives)
                and not any(a.accepted for a in learning.attempts(ex, pack.contentVersion))):
            raise Problem(409, "reserve_variant")
        guide.revealed_at = utc_now()
        learning.bump()
    return {"solution": variant.solution.get(local(learning, locale)), "revision": learning.learner.revision}


@api.get("/exercises/{key}/attempts")
def attempts(key: str, learning: Current) -> dict[str, Any]:
    pair = learning.content.exercises.get(key)
    if not pair:
        raise Problem(404, "not_found")
    return learning.result(pair[0].id)["practices"][key]  # type: ignore[no-any-return]


@api.get("/exercises/{key}/starter/{variant_id}")
def starter(key: str, variant_id: str, learning: Current) -> FileResponse:
    suite = learning.content.suites.get((key, variant_id))
    if not suite:
        raise Problem(404, "not_found")
    return FileResponse(learning.content.file("starters", suite.starter),
                        media_type="text/plain", filename=suite.starter)


@api.get("/examples/{key}/{name}")
def example(key: str, name: str, learning: Current) -> FileResponse:
    if name not in {e.file for e in selected(learning, key).examples}:
        raise Problem(404, "not_found")
    return FileResponse(learning.content.file("examples", name), media_type="text/plain", filename=name)


@api.post("/exercises/{key}/challenges")
def challenge(key: str, body: VariantRequest, learning: Current, request: Request) -> dict[str, Any]:
    _, ex, variant = task(learning, key, body.variantId)
    if request.headers.get("origin") is not None and not request.headers.get("authorization"):
        token = runner.active_token(learning)
        if not token:
            raise Problem(409, "runner_token_required")
    else:
        token = runner.authenticate(learning, request.headers.get("authorization"))
    return runner.issue(learning, ex, variant.id, token)


@api.post("/runner/reports")
def upload(body: RunnerReport, learning: Current, request: Request) -> dict[str, Any]:
    token = runner.authenticate(learning, request.headers.get("authorization"))
    return runner.ingest(learning, token, body)
