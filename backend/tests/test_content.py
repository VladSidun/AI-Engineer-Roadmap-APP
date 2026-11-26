import json
import shutil
from pathlib import Path
from subprocess import run
from sys import executable

import pytest
from pydantic import ValidationError

from app.config import ROOT
from app.domain.content import Content, MapLayout, Pack, dependency_order
from app.domain.grading import grade, passes


def load_content() -> Content:
    return Content()


def test_registry_and_packs() -> None:
    content = load_content()
    assert (len(content.modules), len(content.stages), len(content.lessons)) == (10, 20, 80)
    assert len(content.reviews) == 20 and len(content.gates) == 10
    assert [module.id for module in content.modules.values() if module.availability == "published"] == ["M0", "M1", "M2"]
    assert sum(key in content.lessons for key in content.packs) == 24
    assert sum(key in content.reviews for key in content.packs) == 6
    assert sum(key in content.gates for key in content.packs) == 3
    assert len(content.suites) == 81
    assert [milestone.stageId for milestone in content.projects["A"].milestones] == ["W04", "W05", "W06"]
    assert content.order.index("G-M0") < content.order.index("W02-L01")
    assert all(entry.availability == "planned" for key, entry in content.entries.items()
               if key not in content.packs)


@pytest.mark.parametrize(("bad_parent", "message"), [("absent", "unknown prerequisite"), ("W01-L01", "cycle")])
def test_invalid_manifest(tmp_path: Path, bad_parent: str, message: str) -> None:
    target = tmp_path / "curriculum"
    target.mkdir()
    manifest = json.loads((ROOT / "curriculum/manifest.json").read_bytes())
    manifest["lessons"][0]["prerequisites"] = [bad_parent]
    (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        Content(tmp_path)


@pytest.mark.parametrize("field", ["overview", "theory"])
def test_missing_locale(field: str) -> None:
    raw = load_content().packs["W01-L01"].model_dump()
    del raw[field]["uk"]
    with pytest.raises(ValidationError, match=f"{field}.uk"):
        Pack.model_validate(raw)


def test_path_containment(tmp_path: Path) -> None:
    content = load_content()
    outside = tmp_path / "outside.py"
    outside.touch()
    with pytest.raises(KeyError):
        content.file("examples", "../outside.py")
    with pytest.raises(KeyError):
        content.file("starters", "outside.py")


def test_topological_order() -> None:
    assert dependency_order({"B": ["A"], "A": [], "C": ["B"]}) == ["A", "B", "C"]


@pytest.mark.parametrize("invalid", ["edge", "position", "overlap"])
def test_map_layout_matches_registry(invalid: str) -> None:
    content = load_content()
    raw = content.layout.model_dump(by_alias=True)
    assert (len(content.layout.regions), len(content.layout.nodes), len(content.layout.edges)) == (10, 30, 29)
    if invalid == "edge":
        raw["edges"][0]["to"] = "M0"
    elif invalid == "position":
        raw["nodes"][0]["x"] = raw["worldWidth"] + 1
    else:
        raw["nodes"][0]["x"] = raw["nodes"][1]["x"]
        raw["nodes"][0]["y"] = raw["nodes"][1]["y"]
    with pytest.raises(ValueError, match="map geometry"):
        MapLayout.model_validate(raw).validate_registry(content.modules)


def test_scoring_exact_choices_and_integer_threshold() -> None:
    pack = load_content().packs["W01-L04"]
    answers = {question.id: question.correct[:] for question in pack.questions}
    correct, _ = grade(pack, answers)
    assert correct == 5
    answers["Q3"] = ["B"]
    assert grade(pack, answers)[0] == 4
    assert passes(4, 5) and not passes(7, 9) and passes(8, 10) and not passes(0, 0)
    answers["Q3"] = ["B", "B"]
    with pytest.raises(ValueError):
        grade(pack, answers)


@pytest.mark.parametrize("file", ["fixture_trace.py", "join_trace.py"])
def test_examples(file: str, tmp_path: Path) -> None:
    content = load_content()
    example = next(example for pack in content.packs.values() for example in pack.examples if example.file == file)
    path = shutil.copy(content.file("examples", file), tmp_path)
    good = run([executable, path], cwd=tmp_path, capture_output=True, text=True, check=True)
    assert good.stdout.strip() == example.expected
    if file == "join_trace.py":
        no_match = run([executable, path, "--topic", "99"], capture_output=True, text=True, check=True)
        assert no_match.stdout.strip() == "[]"
        invalid = run([executable, path, "--topic", "xyz"], capture_output=True, text=True)
    else:
        invalid = run([executable, path, "--invalid"], capture_output=True, text=True)
    assert invalid.returncode != 0


@pytest.mark.parametrize("example", [
    example for pack in load_content().packs.values() for example in pack.examples
    if example.file.startswith(("w02_", "w03_", "w04_", "w05_", "w06_"))
], ids=lambda x: x.file)
def test_new_examples_run_from_an_isolated_directory(example, tmp_path: Path) -> None:
    path = shutil.copy(load_content().file("examples", example.file), tmp_path)
    result = run([executable, path], cwd=tmp_path, capture_output=True, text=True, check=True, timeout=10)
    assert result.stdout.strip() == example.expected
