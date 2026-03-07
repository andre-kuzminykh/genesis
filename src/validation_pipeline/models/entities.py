import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from validation_pipeline.models.database import Base


class RunState(str, enum.Enum):
    created = "created"
    validating_input = "validating_input"
    enriching = "enriching"
    scoring = "scoring"
    report_ready = "report_ready"
    report_ready_low_confidence = "report_ready_low_confidence"
    failed = "failed"


class Recommendation(str, enum.Enum):
    proceed = "proceed"
    iterate = "iterate"
    reject = "reject"


class ConfidenceLevel(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return uuid.uuid4()


class Idea(Base):
    __tablename__ = "ideas"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    target_user: Mapped[str] = mapped_column(Text, nullable=False)
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_solution: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    validation_runs: Mapped[list["ValidationRun"]] = relationship(
        back_populates="idea", cascade="all, delete-orphan"
    )


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    idea_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ideas.id"), nullable=False
    )
    state: Mapped[RunState] = mapped_column(
        Enum(RunState), nullable=False, default=RunState.created
    )
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("validation_runs.id"), nullable=True
    )
    iteration_number: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=_utcnow
    )

    idea: Mapped["Idea"] = relationship(back_populates="validation_runs")
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(
        back_populates="validation_run", cascade="all, delete-orphan"
    )
    score_card: Mapped["ScoreCard | None"] = relationship(
        back_populates="validation_run", uselist=False, cascade="all, delete-orphan"
    )
    run_events: Mapped[list["RunEvent"]] = relationship(
        back_populates="validation_run", cascade="all, delete-orphan"
    )
    parent_run: Mapped["ValidationRun | None"] = relationship(
        remote_side="ValidationRun.id", foreign_keys=[parent_run_id]
    )


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("validation_runs.id"), nullable=False
    )
    dimension: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel), default=ConfidenceLevel.medium
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    validation_run: Mapped["ValidationRun"] = relationship(back_populates="evidence_items")


class ScoreCard(Base):
    __tablename__ = "score_cards"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("validation_runs.id"), nullable=False, unique=True
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    overall_confidence: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel), nullable=False
    )
    recommendation: Mapped[Recommendation] = mapped_column(
        Enum(Recommendation), nullable=False
    )
    recommendation_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    next_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_questions: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    validation_run: Mapped["ValidationRun"] = relationship(back_populates="score_card")
    dimension_scores: Mapped[list["DimensionScore"]] = relationship(
        back_populates="score_card", cascade="all, delete-orphan"
    )


class DimensionScore(Base):
    __tablename__ = "dimension_scores"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    score_card_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("score_cards.id"), nullable=False
    )
    dimension: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel), nullable=False
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    missing_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    score_card: Mapped["ScoreCard"] = relationship(back_populates="dimension_scores")


class RunEvent(Base):
    __tablename__ = "run_events"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("validation_runs.id"), nullable=False
    )
    from_state: Mapped[str] = mapped_column(String(50), nullable=False)
    to_state: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    validation_run: Mapped["ValidationRun"] = relationship(back_populates="run_events")
