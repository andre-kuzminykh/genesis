"""API routes for the validation pipeline."""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from validation_pipeline.models.database import get_session
from validation_pipeline.models.entities import (
    Idea,
    RunEvent,
    RunState,
    ValidationRun,
)
from validation_pipeline.schemas.validation_run import (
    RerunCreate,
    RunEventResponse,
    RunHistoryResponse,
    RunStatusResponse,
    ValidationReportResponse,
    ValidationRunCreate,
)
from validation_pipeline.services.orchestrator import Orchestrator
from validation_pipeline.services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/validation-runs", tags=["validation"])


async def _run_pipeline(run_id: uuid.UUID) -> None:
    """Run pipeline in background with a fresh session."""
    from validation_pipeline.models.database import get_session_factory

    async with get_session_factory()() as session:
        orchestrator = Orchestrator(session)
        await orchestrator.execute_pipeline(run_id)


@router.post("", response_model=RunStatusResponse, status_code=201)
async def create_validation_run(
    payload: ValidationRunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """FR-1, FR-2, FR-3: Accept idea submission, validate, create run."""
    idea_data = payload.idea

    # Create idea
    idea = Idea(
        title=idea_data.title,
        target_user=idea_data.target_user,
        problem_statement=idea_data.problem_statement,
        proposed_solution=idea_data.proposed_solution,
        assumptions=idea_data.assumptions,
        market_context=idea_data.market_context,
    )
    session.add(idea)
    await session.flush()

    # Create validation run
    run = ValidationRun(idea_id=idea.id, state=RunState.created, iteration_number=1)
    session.add(run)
    await session.flush()

    # Log initial event
    event = RunEvent(
        run_id=run.id,
        from_state="none",
        to_state=RunState.created.value,
        message="Validation run created",
    )
    session.add(event)
    await session.commit()

    logger.info("Created validation run %s for idea %s", run.id, idea.id)

    # Kick off pipeline in background
    background_tasks.add_task(_run_pipeline, run.id)

    return RunStatusResponse.model_validate(run)


@router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run_status(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get current status of a validation run."""
    run = await session.get(ValidationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Validation run not found")
    return RunStatusResponse.model_validate(run)


@router.get("/{run_id}/report", response_model=ValidationReportResponse)
async def get_report(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """FR-6, FR-7, FR-8: Retrieve structured validation report."""
    run = await session.get(ValidationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Validation run not found")

    if run.state not in (RunState.report_ready, RunState.report_ready_low_confidence):
        raise HTTPException(
            status_code=409,
            detail=f"Report not ready. Current state: {run.state.value}",
        )

    generator = ReportGenerator(session)
    report = await generator.generate(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{run_id}/events", response_model=list[RunEventResponse])
async def get_run_events(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """NFR-3: Get state transition log for a run."""
    run = await session.get(ValidationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Validation run not found")

    stmt = (
        select(RunEvent)
        .where(RunEvent.run_id == run_id)
        .order_by(RunEvent.created_at)
    )
    result = await session.execute(stmt)
    events = result.scalars().all()
    return [RunEventResponse.model_validate(e) for e in events]


@router.post("/{run_id}/rerun", response_model=RunStatusResponse, status_code=201)
async def rerun_validation(
    run_id: uuid.UUID,
    payload: RerunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """FR-11, FR-12: Create a new iteration from a prior run."""
    parent_run = await session.get(ValidationRun, run_id)
    if parent_run is None:
        raise HTTPException(status_code=404, detail="Parent validation run not found")

    # Load original idea
    stmt = select(Idea).where(Idea.id == parent_run.idea_id)
    result = await session.execute(stmt)
    original_idea = result.scalar_one()

    # Create new idea (updated or copied)
    if payload.idea_updates:
        u = payload.idea_updates
        new_idea = Idea(
            title=u.title,
            target_user=u.target_user,
            problem_statement=u.problem_statement,
            proposed_solution=u.proposed_solution,
            assumptions=u.assumptions,
            market_context=u.market_context,
        )
    else:
        new_idea = Idea(
            title=original_idea.title,
            target_user=original_idea.target_user,
            problem_statement=original_idea.problem_statement,
            proposed_solution=original_idea.proposed_solution,
            assumptions=original_idea.assumptions,
            market_context=original_idea.market_context,
        )
    session.add(new_idea)
    await session.flush()

    # Count iterations in the chain
    iteration = parent_run.iteration_number + 1

    new_run = ValidationRun(
        idea_id=new_idea.id,
        state=RunState.created,
        parent_run_id=parent_run.id,
        iteration_number=iteration,
    )
    session.add(new_run)
    await session.flush()

    event = RunEvent(
        run_id=new_run.id,
        from_state="none",
        to_state=RunState.created.value,
        message=f"Rerun created from run {parent_run.id} (iteration {iteration})",
    )
    session.add(event)
    await session.commit()

    logger.info("Created rerun %s from parent %s (iteration %d)", new_run.id, parent_run.id, iteration)

    background_tasks.add_task(_run_pipeline, new_run.id)

    return RunStatusResponse.model_validate(new_run)


@router.get("/{run_id}/history", response_model=RunHistoryResponse)
async def get_run_history(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """NFR-11: Get iteration history chain for a run."""
    run = await session.get(ValidationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Validation run not found")

    # Walk up to root
    root_id = run_id
    current = run
    while current.parent_run_id is not None:
        parent = await session.get(ValidationRun, current.parent_run_id)
        if parent is None:
            break
        root_id = parent.id
        current = parent

    # Collect all runs in the chain from root down
    chain = [RunStatusResponse.model_validate(current)]
    visited = {current.id}

    async def _collect_children(parent_id: uuid.UUID):
        stmt = (
            select(ValidationRun)
            .where(ValidationRun.parent_run_id == parent_id)
            .order_by(ValidationRun.created_at)
        )
        result = await session.execute(stmt)
        children = result.scalars().all()
        for child in children:
            if child.id not in visited:
                visited.add(child.id)
                chain.append(RunStatusResponse.model_validate(child))
                await _collect_children(child.id)

    await _collect_children(current.id)
    return RunHistoryResponse(runs=chain)
