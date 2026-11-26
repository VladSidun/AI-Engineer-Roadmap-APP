from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Learner(Base):
    __tablename__ = "learner"
    __table_args__ = (UniqueConstraint("singleton"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    singleton: Mapped[int] = mapped_column(default=1)
    locale: Mapped[str] = mapped_column(String(2), default="uk")
    revision: Mapped[int] = mapped_column(default=0)


class Viewport(Base):
    __tablename__ = "viewport"

    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learner.id"), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    x: Mapped[float | None] = mapped_column(Float())
    y: Mapped[float | None] = mapped_column(Float())
    zoom: Mapped[float | None] = mapped_column(Float())
    selection: Mapped[str | None] = mapped_column(String(32))
    last_stage_id: Mapped[str | None] = mapped_column(String(32))
    last_activity_id: Mapped[str | None] = mapped_column(String(32))


class Progress(Base):
    __tablename__ = "progress"

    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learner.id"), primary_key=True)
    content_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mastered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_due: Mapped[bool] = mapped_column(Boolean, default=False)


class Assessment(Base):
    __tablename__ = "assessment_attempt"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learner.id"), index=True)
    assessment_id: Mapped[str] = mapped_column(String(32))
    version: Mapped[int]
    answers: Mapped[dict[str, list[str]]] = mapped_column(JSON)
    correct: Mapped[int]
    total: Mapped[int]
    passed: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Guidance(Base):
    __tablename__ = "exercise_guidance"

    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learner.id"), primary_key=True)
    exercise_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    variant: Mapped[str] = mapped_column(String(24), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    hints: Mapped[int] = mapped_column(default=0)
    revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Evidence(Base):
    __tablename__ = "exercise_attempt"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learner.id"), index=True)
    exercise_id: Mapped[str] = mapped_column(String(32))
    variant: Mapped[str] = mapped_column(String(24))
    version: Mapped[int]
    verdict: Mapped[str] = mapped_column(String(32))
    accepted: Mapped[bool]
    criteria: Mapped[list[str] | None] = mapped_column(JSON)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RunnerToken(Base):
    __tablename__ = "runner_token"

    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learner.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Challenge(Base):
    __tablename__ = "runner_challenge"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learner.id"), index=True)
    token_digest: Mapped[str] = mapped_column(ForeignKey("runner_token.digest"))
    exercise_id: Mapped[str] = mapped_column(String(32))
    variant: Mapped[str] = mapped_column(String(24))
    version: Mapped[int]
    suite_id: Mapped[str] = mapped_column(String(80))
    suite_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Report(Base):
    __tablename__ = "runner_report"

    id: Mapped[UUID] = mapped_column(ForeignKey("exercise_attempt.id"), primary_key=True)
    challenge_id: Mapped[UUID] = mapped_column(ForeignKey("runner_challenge.id"), unique=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)


class Reward(Base):
    __tablename__ = "xp_event"

    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learner.id"), primary_key=True)
    event_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    amount: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
