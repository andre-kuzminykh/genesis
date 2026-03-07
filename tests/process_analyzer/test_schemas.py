"""Tests for schemas/models — covers FR-1, FR-2, FR-6, FR-7, FR-9, FR-10.

Requirements tested:
  FR-1: System must support text input of at least 20,000 characters.
  FR-2: System must convert raw text into structured process: roles, steps, artifacts, decisions, systems, metrics.
  FR-6: AutomationPoint schema must capture all required fields.
  FR-7: Each automation point must have: stage, manual_action, potential, automation_type, effect, maturity.
  FR-9: TO-BE model must be based on selected automation points only.
  FR-10: HumanRoleProfile must describe shift from routine to supervision / exception handling.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.process_analyzer.schemas.models import (
    ASISModel,
    AutomationMaturity,
    AutomationPoint,
    AutomationType,
    HumanRoleLevel,
    HumanRoleProfile,
    ProcessStep,
    Role,
    SessionData,
    SessionState,
    TOBEModel,
)


# ---------------------------------------------------------------------------
# FR-1: Text input at least 20,000 chars
# ---------------------------------------------------------------------------

class TestTextInputCapacity:
    """FR-1: System must support at least 20,000 chars in one session."""

    def test_session_data_accepts_20k_text(self):
        text = "A" * 20_000
        session = SessionData(raw_text=text)
        assert len(session.raw_text) == 20_000

    def test_session_data_accepts_50k_text(self):
        text = "B" * 50_000
        session = SessionData(raw_text=text)
        assert len(session.raw_text) == 50_000


# ---------------------------------------------------------------------------
# FR-2: Structured process model
# ---------------------------------------------------------------------------

class TestASISModelStructure:
    """FR-2: Raw text → structured process: roles, steps, artifacts, decisions, systems, metrics."""

    def test_asis_contains_all_required_fields(self, sample_asis: ASISModel):
        assert sample_asis.summary
        assert len(sample_asis.roles) >= 1
        assert len(sample_asis.steps) >= 1
        assert len(sample_asis.artifacts) >= 1
        assert len(sample_asis.systems) >= 1

    def test_process_step_has_required_fields(self):
        step = ProcessStep(
            id="step_1",
            name="Review",
            description="Review document",
            actor="Analyst",
        )
        assert step.id
        assert step.name
        assert step.description
        assert step.actor

    def test_process_step_supports_decision_flag(self):
        step = ProcessStep(
            id="step_1",
            name="Approve?",
            description="Decision point",
            actor="Manager",
            is_decision=True,
        )
        assert step.is_decision is True

    def test_process_step_captures_pain_points(self):
        step = ProcessStep(
            id="step_1",
            name="Manual entry",
            description="Slow manual data entry",
            actor="Clerk",
            pain_points=["Slow", "Error-prone"],
        )
        assert len(step.pain_points) == 2

    def test_role_has_responsibilities(self):
        role = Role(
            name="Analyst",
            description="Performs analysis",
            responsibilities=["Data collection", "Report generation"],
        )
        assert len(role.responsibilities) == 2

    def test_asis_has_issues_and_metrics(self, sample_asis: ASISModel):
        assert len(sample_asis.issues) >= 1
        assert len(sample_asis.metrics) >= 1

    def test_asis_has_mermaid_code(self, sample_asis: ASISModel):
        """FR-3: AS-IS must include Mermaid diagram."""
        assert sample_asis.mermaid_code
        assert "sequenceDiagram" in sample_asis.mermaid_code

    def test_asis_minimal_valid(self):
        asis = ASISModel(summary="Minimal process")
        assert asis.summary == "Minimal process"
        assert asis.roles == []
        assert asis.steps == []

    def test_process_step_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            ProcessStep(id="step_1", name="Test")  # missing description, actor


# ---------------------------------------------------------------------------
# FR-6, FR-7: Automation points schema
# ---------------------------------------------------------------------------

class TestAutomationPointSchema:
    """FR-6/FR-7: Each automation point must have full diagnostic info."""

    def test_automation_point_has_all_fields(
        self, sample_automation_points: list[AutomationPoint]
    ):
        for point in sample_automation_points:
            assert point.id
            assert point.step_id
            assert point.stage
            assert point.manual_action
            assert point.potential
            assert point.automation_type in AutomationType
            assert point.effect
            assert point.maturity in AutomationMaturity

    def test_automation_type_enum_values(self):
        assert AutomationType.DETERMINISTIC.value == "deterministic"
        assert AutomationType.INTELLIGENT.value == "intelligent"
        assert AutomationType.HYBRID.value == "hybrid"

    def test_maturity_enum_values(self):
        assert AutomationMaturity.QUICK_WIN.value == "quick_win"
        assert AutomationMaturity.SHORT_TERM.value == "short_term"
        assert AutomationMaturity.STRATEGIC.value == "strategic"

    def test_default_selected_flag(self, sample_automation_points: list[AutomationPoint]):
        quick_wins = [
            p for p in sample_automation_points
            if p.maturity == AutomationMaturity.QUICK_WIN
        ]
        assert all(p.default_selected for p in quick_wins)

    def test_automation_point_rejects_invalid_type(self):
        with pytest.raises(ValidationError):
            AutomationPoint(
                id="ap_x",
                step_id="step_1",
                stage="Test",
                manual_action="Test",
                potential="Test",
                automation_type="invalid_type",
                effect="Test",
                maturity="quick_win",
            )

    def test_automation_point_rejects_invalid_maturity(self):
        with pytest.raises(ValidationError):
            AutomationPoint(
                id="ap_x",
                step_id="step_1",
                stage="Test",
                manual_action="Test",
                potential="Test",
                automation_type="deterministic",
                effect="Test",
                maturity="invalid",
            )


# ---------------------------------------------------------------------------
# FR-9: TO-BE model structure
# ---------------------------------------------------------------------------

class TestTOBEModelSchema:
    """FR-9: TO-BE must reflect selected automation points."""

    def test_tobe_has_summary_and_steps(self, sample_tobe: TOBEModel):
        assert sample_tobe.summary
        assert len(sample_tobe.steps) >= 1

    def test_tobe_has_mermaid(self, sample_tobe: TOBEModel):
        assert sample_tobe.mermaid_code

    def test_tobe_has_rationale(self, sample_tobe: TOBEModel):
        assert len(sample_tobe.changes_rationale) >= 1

    def test_tobe_has_assumptions(self, sample_tobe: TOBEModel):
        assert len(sample_tobe.assumptions) >= 1

    def test_tobe_steps_include_automated_actors(self, sample_tobe: TOBEModel):
        actors = {s.actor for s in sample_tobe.steps}
        automated = {"System", "AI", "RPA Bot"}
        assert actors & automated, "TO-BE must have at least one automated actor"


# ---------------------------------------------------------------------------
# FR-10: Human role profile
# ---------------------------------------------------------------------------

class TestHumanRoleProfileSchema:
    """FR-10: Human role must show shift from routine to supervision/control."""

    def test_human_role_has_all_fields(self, sample_human_role: HumanRoleProfile):
        assert sample_human_role.role_name
        assert sample_human_role.level in HumanRoleLevel
        assert sample_human_role.mission
        assert len(sample_human_role.responsibilities) >= 1
        assert sample_human_role.boundaries
        assert len(sample_human_role.kpis) >= 1

    def test_human_role_levels(self):
        assert HumanRoleLevel.H0_OPERATOR.value == "H0"
        assert HumanRoleLevel.H1_SUPERVISOR.value == "H1"
        assert HumanRoleLevel.H2_MANAGER.value == "H2"
        assert HumanRoleLevel.H3_EXPERT.value == "H3"

    def test_human_role_from_json(self):
        data = {
            "role_name": "Process Supervisor",
            "level": "H1",
            "mission": "Oversee automated workflows",
            "responsibilities": ["Monitor exceptions", "Approve edge cases"],
            "boundaries": "No manual data entry",
            "interactions": ["AI system", "Dashboard"],
            "outputs": ["Exception report"],
            "kpis": ["SLA compliance"],
            "tools": ["Monitoring dashboard"],
        }
        role = HumanRoleProfile(**data)
        assert role.level == HumanRoleLevel.H1_SUPERVISOR
        assert len(role.responsibilities) == 2


# ---------------------------------------------------------------------------
# Session state management
# ---------------------------------------------------------------------------

class TestSessionState:
    """Verify session state transitions and data integrity."""

    def test_session_initial_state(self):
        session = SessionData()
        assert session.state == SessionState.INPUT
        assert session.asis is None
        assert session.tobe is None
        assert session.human_role is None

    def test_session_state_values(self):
        assert SessionState.INPUT.value == "input"
        assert SessionState.TRANSCRIBED.value == "transcribed"
        assert SessionState.ASIS_GENERATED.value == "asis_generated"
        assert SessionState.AUTOMATION_DIAGNOSED.value == "automation_diagnosed"
        assert SessionState.TOBE_GENERATED.value == "tobe_generated"
        assert SessionState.HTML_READY.value == "html_ready"

    def test_session_stores_all_data(
        self, sample_asis, sample_automation_points, sample_tobe, sample_human_role
    ):
        session = SessionData(
            state=SessionState.HTML_READY,
            process_title="Test Process",
            raw_text="Some text",
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_point_ids=["ap_1", "ap_2"],
            tobe=sample_tobe,
            human_role=sample_human_role,
            html_report="<html>report</html>",
        )
        assert session.state == SessionState.HTML_READY
        assert len(session.automation_points) == 4
        assert len(session.selected_point_ids) == 2
        assert session.html_report
