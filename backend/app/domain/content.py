import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.config import ROOT

Locale = Literal["uk", "en"]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ID = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")]
Minutes = Annotated[int, Field(gt=0)]
Availability = Literal["planned", "published"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Localized(Strict):
    uk: Text
    en: Text

    def get(self, locale: Locale) -> str:
        return self.uk if locale == "uk" else self.en


class Named(Strict):
    id: ID
    title: Localized


class Entry(Named):
    prerequisites: list[ID]
    estimateMinutes: Minutes
    availability: Availability
    contentVersion: Minutes


class Module(Entry):
    campaignId: ID
    stageIds: list[ID]
    gateId: ID


class Stage(Entry):
    moduleId: ID
    lessonIds: list[ID]
    reviewId: ID


class StageItem(Entry):
    stageId: ID


class Gate(Entry):
    moduleId: ID


class Milestone(Named):
    stageId: ID
    evidenceId: ID
    artifacts: Annotated[list[Localized], Field(min_length=1)]


class Project(Named):
    start: ID
    availability: Availability
    milestones: list[Milestone] = Field(default_factory=list)


class Manifest(Strict):
    schemaVersion: Literal[1]
    curriculumVersion: Text
    campaigns: list[Named]
    modules: list[Module]
    stages: list[Stage]
    lessons: list[StageItem]
    reviews: list[StageItem]
    gates: list[Gate]
    projects: list[Project]
    skills: list[ID]


Point = tuple[int, int]


class MapRegion(Strict):
    id: ID
    x: int
    y: int
    polygon: Annotated[list[Point], Field(min_length=3)]


class MapNode(Strict):
    id: ID
    x: int
    y: int
    kind: Literal["stage", "gate"]


class MapEdge(Strict):
    from_id: ID = Field(alias="from")
    to: ID
    waypoints: list[Point]


class MapLayout(Strict):
    schemaVersion: Literal[1]
    worldWidth: Annotated[int, Field(gt=0, le=10000)]
    worldHeight: Annotated[int, Field(gt=0, le=10000)]
    regions: list[MapRegion]
    nodes: list[MapNode]
    edges: list[MapEdge]

    def validate_registry(self, modules: dict[str, Module]) -> None:
        expected = [
            (key, "gate" if key == module.gateId else "stage")
            for module in modules.values() for key in (*module.stageIds, module.gateId)
        ]
        anchors = [(entry.x, entry.y) for entry in self.regions] + [
            (entry.x, entry.y) for entry in self.nodes
        ]
        all_points = anchors + [p for region in self.regions for p in region.polygon] + [
            p for edge in self.edges for p in edge.waypoints
        ]
        if (
            [region.id for region in self.regions] != list(modules)
            or [(node.id, node.kind) for node in self.nodes] != expected
            or [(edge.from_id, edge.to) for edge in self.edges]
            != [(left[0], right[0]) for left, right in zip(expected, expected[1:])]
            or len(anchors) != len(set(anchors))
            or any(not (0 <= x <= self.worldWidth and 0 <= y <= self.worldHeight)
                   for x, y in all_points)
        ):
            raise ValueError("map geometry does not match campaign registry")


class Objective(Named):
    skill: ID


class Option(Named):
    explanation: Localized


class Question(Strict):
    id: ID
    prompt: Localized
    objectives: Annotated[list[ID], Field(min_length=1)]
    options: Annotated[list[Option], Field(min_length=3, max_length=6)]
    correct: Annotated[list[ID], Field(min_length=1)]

    @model_validator(mode="after")
    def options_match(self) -> "Question":
        ids = {option.id for option in self.options}
        if (len(ids) != len(self.options) or len(set(self.correct)) != len(self.correct)
                or not set(self.correct) < ids):
            raise ValueError("invalid answer IDs")
        return self


class Variant(Named):
    prompt: Localized
    hints: tuple[Localized, Localized, Localized]
    solution: Localized


class Exercise(Named):
    kind: Literal["code", "rubric"]
    objectives: Annotated[list[ID], Field(min_length=1)]
    estimateMinutes: Minutes
    criteria: list[Named]
    example: Localized
    variants: Annotated[list[Variant], Field(min_length=1)]
    diagnostic: bool = False

    @model_validator(mode="after")
    def check_kind(self) -> "Exercise":
        ids = unique(self.variants)
        unique(self.criteria)
        if self.kind == "code" and (self.criteria or not {"v1", "v2", "v3"} <= ids.keys()):
            raise ValueError("code exercises need primary and two retry variants")
        if self.kind == "rubric" and (not self.criteria or self.diagnostic):
            raise ValueError("rubric criteria and provenance required")
        return self


class Source(Strict):
    title: Localized
    url: Annotated[str, StringConstraints(pattern=r"^https://[a-z0-9.-]+/[^\s]*$")]
    checked: Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    version: Text


class Example(Strict):
    file: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*\.py$")]
    explanation: Localized
    expected: Text
    error: Localized


class Pack(Strict):
    id: ID
    contentVersion: Minutes
    objectives: Annotated[list[Objective], Field(min_length=2, max_length=4)]
    overview: Localized
    theory: Localized
    recap: Localized
    interview: Annotated[list[Text], Field(min_length=2, max_length=3)]
    interviewGuide: Localized
    sources: Annotated[list[Source], Field(min_length=1)]
    examples: list[Example]
    questions: list[Question]
    exercises: Annotated[list[Exercise], Field(min_length=1)]
    crosslinks: Annotated[list[ID], Field(min_length=1)]


class Suite(Strict):
    id: ID
    exerciseId: ID
    variantId: ID
    contentVersion: Minutes
    testIds: Annotated[list[ID], Field(min_length=1, max_length=30)]
    digest: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    starter: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*\.py$")]
    source: Literal["m0.py", "m1.py", "m2.py"] = "m0.py"


def unique[T: Named | Pack | Question | Suite](items: list[T]) -> dict[str, T]:
    indexed = {item.id: item for item in items}
    if len(indexed) != len(items):
        raise ValueError("duplicate content ID")
    return indexed


def dependency_order(graph: dict[str, list[str]]) -> list[str]:
    order: list[str] = []
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(node: str) -> None:
        if node in done:
            return
        if node in visiting:
            raise ValueError(f"cycle at {node}")
        if node not in graph:
            raise ValueError(f"unknown prerequisite {node}")
        visiting.add(node)
        for parent in graph[node]:
            visit(parent)
        visiting.remove(node)
        done.add(node)
        order.append(node)

    for entry in graph:
        visit(entry)
    return order


def suite_digest(source: bytes, suite: dict[str, object]) -> str:
    data = {key: value for key, value in suite.items()
            if key != "digest" and (key != "source" or value != "m0.py")}
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return sha256(source.replace(b"\r\n", b"\n") + b"\0" + canonical).hexdigest()


class Content:
    def __init__(self, root: Path = ROOT):
        curriculum = root / "curriculum"
        self.root = curriculum
        self.manifest = Manifest.model_validate_json((curriculum / "manifest.json").read_bytes())
        self.modules = unique(self.manifest.modules)
        self.stages = unique(self.manifest.stages)
        self.lessons = unique(self.manifest.lessons)
        self.reviews = unique(self.manifest.reviews)
        self.gates = unique(self.manifest.gates)
        self.projects = unique(self.manifest.projects)
        self.entries: dict[str, Entry] = {**self.lessons, **self.reviews, **self.gates}
        all_nodes: dict[str, Entry] = {**self.modules, **self.stages, **self.entries}
        self.order = dependency_order({key: entry.prerequisites for key, entry in all_nodes.items()})
        self._validate_registry()
        self.layout = MapLayout.model_validate_json((curriculum / "map-layout.json").read_bytes())
        self.layout.validate_registry(self.modules)
        expected = {key for key, entry in self.entries.items() if entry.availability == "published"}
        package = curriculum / "packs"
        actual = {path.stem for path in package.glob("*.json")}
        if actual != expected:
            raise ValueError("published packs and registry differ")
        self.packs = unique([
            Pack.model_validate_json((package / f"{key}.json").read_bytes())
            for key in sorted(expected)
        ])
        if self.packs.keys() != expected:
            raise ValueError("pack ID does not match registry")
        suites_dir = root / "runner" / "quest_runner" / "suites"
        suites = unique([Suite.model_validate(row) for row in
                         json.loads((suites_dir / "catalog.json").read_bytes())])
        self.suites = {(s.exerciseId, s.variantId): s for s in suites.values()}
        sources = {name: (suites_dir / name).read_bytes() for name in {row.source for row in suites.values()}}
        for suite in suites.values():
            if (len(suite.testIds) != len(set(suite.testIds))
                    or suite.digest != suite_digest(sources[suite.source], suite.model_dump())):
                raise ValueError(f"invalid suite {suite.id}")
            self.file("starters", suite.starter)
        self.exercises: dict[str, tuple[Pack, Exercise]] = {}
        self._validate_packs()
        required = {(e.id, v.id) for _, e in self.exercises.values()
                    if e.kind == "code" for v in e.variants}
        if self.suites.keys() != required or len(suites) != len(self.suites):
            raise ValueError("unreferenced or duplicate suite")

    def _validate_registry(self) -> None:
        if list(unique(self.manifest.campaigns)) != ["main"]:
            raise ValueError("invalid main campaign")
        stages = [f"W{i:02}" for i in range(1, 21)]
        modules = [f"M{i}" for i in range(10)]
        if list(self.modules) != modules or list(self.stages) != stages:
            raise ValueError("invalid module or stage IDs")
        if list(self.lessons) != [f"{w}-L{i:02}" for w in stages for i in range(1, 5)]:
            raise ValueError("invalid lesson IDs")
        if list(self.reviews) != [f"SR-{w}" for w in stages] or list(self.gates) != [
            f"G-{m}" for m in modules
        ]:
            raise ValueError("invalid review or challenge IDs")
        numbers = [1, 2, 3, 2, 2, 1, 3, 2, 3, 1]
        start = 0
        for i, m in enumerate(self.modules.values()):
            prerequisites = [f"G-M{i - 1}"] if i else []
            if (m.stageIds != stages[start:start + numbers[i]] or m.gateId != f"G-{m.id}"
                    or m.campaignId != "main" or m.prerequisites != prerequisites):
                raise ValueError(f"invalid module {m.id}")
            self.check_entry(self.gates[m.gateId], m, [f"SR-{w}" for w in m.stageIds])
            if self.gates[m.gateId].moduleId != m.id:
                raise ValueError("invalid gate owner")
            for w in m.stageIds:
                stage = self.stages[w]
                self.check_entry(stage, m, prerequisites)
                lessons = [f"{w}-L{i:02}" for i in range(1, 5)]
                if stage.moduleId != m.id or stage.lessonIds != lessons or stage.reviewId != f"SR-{w}":
                    raise ValueError(f"invalid stage {w}")
                for key in lessons:
                    lesson = self.lessons[key]
                    self.check_entry(lesson, m, prerequisites)
                    if lesson.stageId != w:
                        raise ValueError(f"invalid lesson stage {key}")
                    prerequisites = [key]
                review = self.reviews[stage.reviewId]
                self.check_entry(review, m, lessons)
                if review.stageId != w:
                    raise ValueError("invalid review stage")
                prerequisites = [review.id]
            start += numbers[i]
        for project in self.projects.values():
            if project.start not in self.stages:
                raise ValueError("invalid project stage")
            milestones = list(unique(project.milestones).values())
            if not milestones:
                if project.availability == "published":
                    raise ValueError("published project needs milestones")
                continue
            stages_for_project = [milestone.stageId for milestone in milestones]
            if (project.availability != "published" or stages_for_project[0] != project.start
                    or len(stages_for_project) != len(set(stages_for_project))
                    or [key for key in self.stages if key in stages_for_project] != stages_for_project):
                raise ValueError("invalid project milestone sequence")
            for milestone in milestones:
                stage = self.stages[milestone.stageId]
                if (stage.availability != "published" or milestone.evidenceId != stage.reviewId
                        or not milestone.id.startswith(f"{project.id}-")):
                    raise ValueError("invalid milestone evidence")

    @staticmethod
    def check_entry(entry: Entry, module: Module, prerequisites: list[str]) -> None:
        if entry.prerequisites != prerequisites or entry.availability != module.availability:
            raise ValueError(f"invalid sequence or availability: {entry.id}")

    def _validate_packs(self) -> None:
        for pack in self.packs.values():
            minimum, maximum = (4, 6) if pack.id in self.lessons else (
                (8, 10) if pack.id in self.reviews else (10, 15)
            )
            if (not minimum <= len(pack.questions) <= maximum
                    or pack.contentVersion != self.entries[pack.id].contentVersion
                    or (pack.id in self.lessons and len(pack.exercises) != 2)
                    or set(pack.crosslinks) - self.entries.keys() or pack.id in pack.crosslinks):
                raise ValueError(f"incomplete pack {pack.id}")
            objs = unique(pack.objectives)
            if {o.skill for o in objs.values()} - set(self.manifest.skills):
                raise ValueError("unknown skill")
            for i, question in enumerate(unique(pack.questions).values(), 1):
                if question.id != f"Q{i}" or set(question.objectives) - objs.keys():
                    raise ValueError("invalid question references")
            for i, exercise in enumerate(unique(pack.exercises).values(), 1):
                if (exercise.id != f"{pack.id}-E{i}" or set(exercise.objectives) - objs.keys()
                        or exercise.id in self.exercises):
                    raise ValueError("invalid exercise references")
                self.exercises[exercise.id] = (pack, exercise)
                if exercise.kind == "code":
                    for variant in exercise.variants:
                        suite = self.suites.get((exercise.id, variant.id))
                        if suite is None or suite.contentVersion != pack.contentVersion:
                            raise ValueError(f"missing suite for {exercise.id}/{variant.id}")
            for example in pack.examples:
                self.file("examples", example.file)

    def file(self, directory: Literal["examples", "starters"], name: str) -> Path:
        if not re.fullmatch(r"[a-z][a-z0-9_]*\.py", name):
            raise KeyError(name)
        base = (self.root / "labs" / directory).resolve()
        path = (base / name).resolve()
        if path.parent != base or not path.is_file():
            raise KeyError(name)
        return path


if __name__ == "__main__":
    content = Content()
    print(f"{len(content.modules)} modules, {len(content.stages)} stages, "
          f"{len(content.lessons)} lessons, {len(content.gates)} gates, "
          f"{len(content.packs)} bilingual packs, {len(content.suites)} suites")
