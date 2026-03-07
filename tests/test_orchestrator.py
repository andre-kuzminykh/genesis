"""Integration tests for the orchestrator pipeline."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from validation_pipeline.models.entities import (
    EvidenceItem,
    Idea,
    RunState,
    ScoreCard,
    ValidationRun,
)
from validation_pipeline.services.orchestrator import Orchestrator


async def _create_idea_and_run(session: AsyncSession) -> ValidationRun:
    idea = Idea(
        title="Test idea for orchestrator",
        target_user="Software developers who need faster CI/CD pipelines and automated testing",
        problem_statement=(
            "CI/CD pipelines are slow and require manual configuration. "
            "Developers spend too much time waiting for builds and fixing pipeline issues."
        ),
        proposed_solution=(
            "Build an intelligent CI/CD optimizer that automatically tunes pipeline "
            "configurations, parallelizes builds, and predicts failures early."
        ),
        assumptions="Teams use standard CI tools like GitHub Actions or GitLab CI.",
        market_context="DevOps market growing rapidly. CI/CD is a critical pain point.",
    )
    session.add(idea)
    await session.flush()

    run = ValidationRun(idea_id=idea.id, state=RunState.created)
    session.add(run)
    await session.commit()
    return run


@pytest.mark.asyncio
async def test_pipeline_success(session: AsyncSession):
    run = await _create_idea_and_run(session)
    orchestrator = Orchestrator(session)
    await orchestrator.execute_pipeline(run.id)

    await session.refresh(run)
    assert run.state in (RunState.report_ready, RunState.report_ready_low_confidence)

    # Check evidence was created
    stmt = select(EvidenceItem).where(EvidenceItem.run_id == run.id)
    result = await session.execute(stmt)
    evidence = list(result.scalars().all())
    assert len(evidence) == 6  # one per dimension

    # Check score card
    stmt = select(ScoreCard).where(ScoreCard.run_id == run.id)
    result = await session.execute(stmt)
    card = result.scalar_one()
    assert card.overall_score > 0
    assert card.recommendation is not None


@pytest.mark.asyncio
async def test_pipeline_minimal_idea(session: AsyncSession):
    """Test with minimal content — should still complete but with lower confidence."""
    idea = Idea(
        title="Minimal idea",
        target_user="Users who need help",
        problem_statement="There is a problem that needs solving somehow.",
        proposed_solution="Build something to fix it.",
    )
    session.add(idea)
    await session.flush()

    run = ValidationRun(idea_id=idea.id, state=RunState.created)
    session.add(run)
    await session.commit()

    orchestrator = Orchestrator(session)
    await orchestrator.execute_pipeline(run.id)

    await session.refresh(run)
    assert run.state in (RunState.report_ready, RunState.report_ready_low_confidence)
