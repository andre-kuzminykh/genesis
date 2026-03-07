"""Report generator — assembles the final validation report."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from validation_pipeline.models.entities import (
    EvidenceItem,
    ScoreCard,
    ValidationRun,
)
from validation_pipeline.schemas.idea import IdeaResponse
from validation_pipeline.schemas.validation_run import (
    DimensionScoreResponse,
    EvidenceItemResponse,
    RunStatusResponse,
    ScoreCardResponse,
    ValidationReportResponse,
)


class ReportGenerator:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate(self, run_id: uuid.UUID) -> ValidationReportResponse | None:
        stmt = (
            select(ValidationRun)
            .options(
                selectinload(ValidationRun.idea),
                selectinload(ValidationRun.score_card).selectinload(
                    ScoreCard.dimension_scores
                ),
                selectinload(ValidationRun.evidence_items),
            )
            .where(ValidationRun.id == run_id)
        )
        result = await self.session.execute(stmt)
        run = result.scalar_one_or_none()
        if run is None:
            return None

        run_resp = RunStatusResponse.model_validate(run)
        idea_resp = IdeaResponse.model_validate(run.idea)

        score_card_resp = None
        if run.score_card:
            dim_scores = [
                DimensionScoreResponse.model_validate(ds)
                for ds in run.score_card.dimension_scores
            ]
            score_card_resp = ScoreCardResponse(
                overall_score=run.score_card.overall_score,
                overall_confidence=run.score_card.overall_confidence.value,
                recommendation=run.score_card.recommendation.value,
                recommendation_rationale=run.score_card.recommendation_rationale,
                next_steps=run.score_card.next_steps,
                follow_up_questions=run.score_card.follow_up_questions,
                dimension_scores=dim_scores,
            )

        evidence_resp = [
            EvidenceItemResponse.model_validate(e) for e in run.evidence_items
        ]

        return ValidationReportResponse(
            run=run_resp,
            idea=idea_resp,
            score_card=score_card_resp,
            evidence=evidence_resp,
        )
