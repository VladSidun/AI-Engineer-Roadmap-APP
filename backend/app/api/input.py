from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from app.domain.content import ID, Locale, Strict


class Preferences(Strict):
    locale: Locale


Coordinate = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class CameraInput(Strict):
    x: Coordinate
    y: Coordinate
    zoom: Coordinate
    selection: ID


class ViewportInput(Strict):
    camera: CameraInput | None = None
    lastStageId: ID | None = None
    lastActivityId: ID | None = None

    @model_validator(mode="after")
    def assert_update(self) -> "ViewportInput":
        if self.camera is None and self.lastStageId is None and self.lastActivityId is None:
            raise ValueError("viewport update is empty")
        return self


class QuizAnswers(Strict):
    submissionId: UUID
    answers: Annotated[dict[ID, Annotated[list[ID], Field(min_length=1, max_length=6)]],
                       Field(min_length=1, max_length=15)]


class VariantRequest(Strict):
    variantId: ID = "v1"


class Rubric(VariantRequest):
    submissionId: UUID
    criteria: Annotated[list[ID], Field(min_length=1, max_length=12)]
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=3000)]


class TestCase(Strict):
    id: ID
    status: Literal["passed", "failed", "skipped", "error"]


class RunnerReport(Strict):
    schemaVersion: Literal[1]
    challengeId: UUID
    reportId: UUID
    exerciseId: ID
    variantId: ID
    contentVersion: Annotated[int, Field(strict=True, ge=1, le=100000)]
    suiteId: ID
    suiteDigest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    startedAt: AwareDatetime
    durationMs: Annotated[int, Field(strict=True, ge=0, le=600000)]
    exitCode: Annotated[int, Field(strict=True, ge=-255, le=255)]
    expectedIds: Annotated[list[ID], Field(min_length=1, max_length=30)]
    cases: Annotated[list[TestCase], Field(max_length=30)]
    runnerVersion: Literal["1.0.0"]

    def started(self) -> datetime:
        return self.startedAt
