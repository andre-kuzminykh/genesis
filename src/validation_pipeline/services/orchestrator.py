"""Validation pipeline orchestrator — executes the state machine for a run."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from validation_pipeline.models.entities import (
    ConfidenceLevel,
    EvidenceItem,
    Recommendation,
    RunEvent,
    RunState,
    ScoreCard,
    ValidationRun,
)
from validation_pipeline.services.scoring import ScoringEngine

logger = logging.getLogger(__name__)

VALIDATION_DIMENSIONS = [
    "problem_clarity",
    "target_user_definition",
    "market_opportunity",
    "solution_feasibility",
    "competitive_landscape",
    "assumptions_risk",
]


class Orchestrator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.scoring = ScoringEngine()

    async def execute_pipeline(self, run_id: uuid.UUID) -> None:
        run = await self._load_run(run_id)
        if run is None:
            logger.error("Run %s not found", run_id)
            return

        try:
            await self._transition(run, RunState.validating_input, "Starting input validation")
            await self._validate_input(run)

            await self._transition(run, RunState.enriching, "Collecting evidence")
            await self._enrich(run)

            await self._transition(run, RunState.scoring, "Scoring idea")
            score_card = await self._score(run)

            final_state = (
                RunState.report_ready_low_confidence
                if score_card.overall_confidence == ConfidenceLevel.low
                else RunState.report_ready
            )
            await self._transition(run, final_state, "Report ready")

        except Exception as e:
            logger.exception("Pipeline failed for run %s", run_id)
            await self._transition(run, RunState.failed, f"Pipeline error: {e}")

    async def _load_run(self, run_id: uuid.UUID) -> ValidationRun | None:
        stmt = (
            select(ValidationRun)
            .options(selectinload(ValidationRun.idea))
            .where(ValidationRun.id == run_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _transition(
        self, run: ValidationRun, to_state: RunState, message: str
    ) -> None:
        from_state = run.state
        run.state = to_state
        event = RunEvent(
            run_id=run.id,
            from_state=from_state.value if isinstance(from_state, RunState) else from_state,
            to_state=to_state.value,
            message=message,
        )
        self.session.add(event)
        await self.session.commit()
        logger.info("Run %s: %s → %s (%s)", run.id, from_state, to_state, message)

    async def _validate_input(self, run: ValidationRun) -> None:
        idea = run.idea
        if not idea.title or not idea.problem_statement:
            raise ValueError("Idea missing required fields")

    async def _enrich(self, run: ValidationRun) -> None:
        idea = run.idea
        for dimension in VALIDATION_DIMENSIONS:
            evidence = self._generate_evidence(dimension, idea)
            item = EvidenceItem(
                run_id=run.id,
                dimension=dimension,
                source="internal_analysis",
                content=evidence["content"],
                confidence=evidence["confidence"],
            )
            self.session.add(item)
        await self.session.commit()

    def _generate_evidence(self, dimension: str, idea) -> dict:
        """Generate evidence for a dimension based on idea content.

        In production this would call external research providers / LLMs.
        For MVP, we use heuristic analysis.
        """
        evidence_map = {
            "problem_clarity": {
                "content": (
                    f"Problem statement analysis: '{idea.problem_statement[:200]}...' — "
                    f"The problem is articulated with "
                    f"{'sufficient' if len(idea.problem_statement) > 50 else 'insufficient'} detail."
                ),
                "confidence": (
                    ConfidenceLevel.high
                    if len(idea.problem_statement) > 100
                    else ConfidenceLevel.medium
                    if len(idea.problem_statement) > 30
                    else ConfidenceLevel.low
                ),
            },
            "target_user_definition": {
                "content": (
                    f"Target user analysis: '{idea.target_user[:200]}' — "
                    f"User persona is "
                    f"{'well' if len(idea.target_user) > 50 else 'loosely'}-defined."
                ),
                "confidence": (
                    ConfidenceLevel.high
                    if len(idea.target_user) > 100
                    else ConfidenceLevel.medium
                ),
            },
            "market_opportunity": {
                "content": (
                    f"Market context: {idea.market_context or 'No market context provided.'} — "
                    f"{'Market analysis available.' if idea.market_context else 'Market data missing.'}"
                ),
                "confidence": (
                    ConfidenceLevel.medium if idea.market_context else ConfidenceLevel.low
                ),
            },
            "solution_feasibility": {
                "content": (
                    f"Solution analysis: '{idea.proposed_solution[:200]}...' — "
                    f"Feasibility assessment based on solution description."
                ),
                "confidence": (
                    ConfidenceLevel.high
                    if len(idea.proposed_solution) > 100
                    else ConfidenceLevel.medium
                ),
            },
            "competitive_landscape": {
                "content": "Competitive analysis: No external competitive data available for MVP.",
                "confidence": ConfidenceLevel.low,
            },
            "assumptions_risk": {
                "content": (
                    f"Assumptions: {idea.assumptions or 'No assumptions stated.'} — "
                    f"{'Assumptions documented for review.' if idea.assumptions else 'Risk elevated due to unstated assumptions.'}"
                ),
                "confidence": (
                    ConfidenceLevel.medium if idea.assumptions else ConfidenceLevel.low
                ),
            },
        }
        return evidence_map.get(
            dimension,
            {"content": "No analysis available.", "confidence": ConfidenceLevel.low},
        )

    async def _score(self, run: ValidationRun) -> ScoreCard:
        stmt = select(EvidenceItem).where(EvidenceItem.run_id == run.id)
        result = await self.session.execute(stmt)
        evidence_items = list(result.scalars().all())

        score_card = self.scoring.score(run, evidence_items)
        self.session.add(score_card)
        for ds in score_card.dimension_scores:
            self.session.add(ds)
        await self.session.commit()
        return score_card
