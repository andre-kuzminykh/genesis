import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from validation_pipeline.schemas.idea import IdeaCreate, IdeaResponse


class ValidationRunCreate(BaseModel):
    idea: IdeaCreate


class RerunCreate(BaseModel):
    idea_updates: IdeaCreate | None = Field(
        None, description="Updated idea fields. If None, reuses the original idea."
    )


class RunStatusResponse(BaseModel):
    id: uuid.UUID
    idea_id: uuid.UUID
    state: str
    parent_run_id: uuid.UUID | None
    iteration_number: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DimensionScoreResponse(BaseModel):
    dimension: str
    score: float
    confidence: str
    rationale: str
    missing_evidence: str | None

    model_config = {"from_attributes": True}


class EvidenceItemResponse(BaseModel):
    id: uuid.UUID
    dimension: str
    source: str
    content: str
    confidence: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ScoreCardResponse(BaseModel):
    overall_score: float
    overall_confidence: str
    recommendation: str
    recommendation_rationale: str
    next_steps: str | None
    follow_up_questions: str | None
    dimension_scores: list[DimensionScoreResponse]

    model_config = {"from_attributes": True}


class ValidationReportResponse(BaseModel):
    run: RunStatusResponse
    idea: IdeaResponse
    score_card: ScoreCardResponse | None
    evidence: list[EvidenceItemResponse]


class RunEventResponse(BaseModel):
    from_state: str
    to_state: str
    message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunHistoryResponse(BaseModel):
    runs: list[RunStatusResponse]


class FieldError(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    detail: str = "Validation failed"
    errors: list[FieldError]
