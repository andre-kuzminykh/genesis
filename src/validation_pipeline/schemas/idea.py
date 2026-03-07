import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class IdeaCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=500, description="Idea title")
    target_user: str = Field(..., min_length=5, max_length=2000, description="Target user persona")
    problem_statement: str = Field(
        ..., min_length=10, max_length=5000, description="Problem being solved"
    )
    proposed_solution: str = Field(
        ..., min_length=10, max_length=5000, description="Proposed solution"
    )
    assumptions: str | None = Field(None, max_length=3000, description="Key assumptions")
    market_context: str | None = Field(None, max_length=3000, description="Market/context notes")


class IdeaResponse(BaseModel):
    id: uuid.UUID
    title: str
    target_user: str
    problem_statement: str
    proposed_solution: str
    assumptions: str | None
    market_context: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
