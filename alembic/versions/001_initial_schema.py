"""Initial schema for idea validation pipeline.

Revision ID: 001
Revises:
Create Date: 2026-03-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ideas table
    op.create_table(
        "ideas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("target_user", sa.Text, nullable=False),
        sa.Column("problem_statement", sa.Text, nullable=False),
        sa.Column("proposed_solution", sa.Text, nullable=False),
        sa.Column("assumptions", sa.Text, nullable=True),
        sa.Column("market_context", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Run states enum
    run_state = postgresql.ENUM(
        "created",
        "validating_input",
        "enriching",
        "scoring",
        "report_ready",
        "report_ready_low_confidence",
        "failed",
        name="runstate",
        create_type=True,
    )

    confidence_level = postgresql.ENUM(
        "high", "medium", "low", name="confidencelevel", create_type=True
    )

    recommendation = postgresql.ENUM(
        "proceed", "iterate", "reject", name="recommendation", create_type=True
    )

    # Validation runs table
    op.create_table(
        "validation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "idea_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ideas.id"),
            nullable=False,
        ),
        sa.Column("state", run_state, nullable=False, server_default="created"),
        sa.Column(
            "parent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_runs.id"),
            nullable=True,
        ),
        sa.Column("iteration_number", sa.Integer, default=1),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Evidence items table
    op.create_table(
        "evidence_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_runs.id"),
            nullable=False,
        ),
        sa.Column("dimension", sa.String(100), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("confidence", confidence_level, server_default="medium"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Score cards table
    op.create_table(
        "score_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_runs.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("overall_score", sa.Float, nullable=False),
        sa.Column("overall_confidence", confidence_level, nullable=False),
        sa.Column("recommendation", recommendation, nullable=False),
        sa.Column("recommendation_rationale", sa.Text, nullable=False),
        sa.Column("next_steps", sa.Text, nullable=True),
        sa.Column("follow_up_questions", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Dimension scores table
    op.create_table(
        "dimension_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "score_card_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("score_cards.id"),
            nullable=False,
        ),
        sa.Column("dimension", sa.String(100), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("confidence", confidence_level, nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("missing_evidence", sa.Text, nullable=True),
    )

    # Run events table
    op.create_table(
        "run_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_runs.id"),
            nullable=False,
        ),
        sa.Column("from_state", sa.String(50), nullable=False),
        sa.Column("to_state", sa.String(50), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("run_events")
    op.drop_table("dimension_scores")
    op.drop_table("score_cards")
    op.drop_table("evidence_items")
    op.drop_table("validation_runs")
    op.drop_table("ideas")
    op.execute("DROP TYPE IF EXISTS runstate")
    op.execute("DROP TYPE IF EXISTS confidencelevel")
    op.execute("DROP TYPE IF EXISTS recommendation")
