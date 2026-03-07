"""Tests for prompt templates — ensure all templates are valid and contain required placeholders."""

from __future__ import annotations

from src.process_analyzer.prompts.templates import (
    ASIS_MERMAID_SYSTEM,
    ASIS_MERMAID_USER,
    ASIS_SYSTEM,
    ASIS_USER,
    AUTOMATION_SYSTEM,
    AUTOMATION_USER,
    HUMAN_ROLE_SYSTEM,
    HUMAN_ROLE_USER,
    TOBE_MERMAID_USER,
    TOBE_SYSTEM,
    TOBE_USER,
)


class TestASISPrompts:
    def test_asis_system_prompt_non_empty(self):
        assert len(ASIS_SYSTEM) > 50
        assert "JSON" in ASIS_SYSTEM

    def test_asis_user_prompt_has_placeholders(self):
        assert "{title}" in ASIS_USER
        assert "{text}" in ASIS_USER

    def test_asis_user_prompt_describes_schema(self):
        assert "summary" in ASIS_USER
        assert "roles" in ASIS_USER
        assert "steps" in ASIS_USER
        assert "artifacts" in ASIS_USER
        assert "pain_points" in ASIS_USER

    def test_asis_user_prompt_format_works(self):
        result = ASIS_USER.format(title="Test Process", text="Some process description")
        assert "Test Process" in result
        assert "Some process description" in result


class TestASISMermaidPrompts:
    def test_mermaid_system_non_empty(self):
        assert len(ASIS_MERMAID_SYSTEM) > 20
        assert "Mermaid" in ASIS_MERMAID_SYSTEM

    def test_mermaid_user_has_placeholders(self):
        assert "{title}" in ASIS_MERMAID_USER
        assert "{steps_json}" in ASIS_MERMAID_USER
        assert "{roles_json}" in ASIS_MERMAID_USER

    def test_mermaid_user_requires_sequence_diagram(self):
        assert "sequenceDiagram" in ASIS_MERMAID_USER


class TestAutomationPrompts:
    def test_automation_system_non_empty(self):
        assert len(AUTOMATION_SYSTEM) > 50
        assert "JSON" in AUTOMATION_SYSTEM

    def test_automation_user_has_placeholders(self):
        assert "{title}" in AUTOMATION_USER
        assert "{summary}" in AUTOMATION_USER
        assert "{steps_json}" in AUTOMATION_USER

    def test_automation_user_describes_fields(self):
        assert "automation_type" in AUTOMATION_USER
        assert "maturity" in AUTOMATION_USER
        assert "effect" in AUTOMATION_USER
        assert "manual_action" in AUTOMATION_USER

    def test_automation_user_describes_types(self):
        assert "deterministic" in AUTOMATION_USER
        assert "intelligent" in AUTOMATION_USER
        assert "hybrid" in AUTOMATION_USER

    def test_automation_user_describes_maturity_levels(self):
        assert "quick_win" in AUTOMATION_USER
        assert "short_term" in AUTOMATION_USER
        assert "strategic" in AUTOMATION_USER


class TestTOBEPrompts:
    def test_tobe_system_non_empty(self):
        assert len(TOBE_SYSTEM) > 50
        assert "JSON" in TOBE_SYSTEM

    def test_tobe_user_has_placeholders(self):
        assert "{title}" in TOBE_USER
        assert "{asis_summary}" in TOBE_USER
        assert "{asis_steps_json}" in TOBE_USER
        assert "{selected_points_json}" in TOBE_USER

    def test_tobe_mermaid_user_has_placeholders(self):
        assert "{title}" in TOBE_MERMAID_USER
        assert "{steps_json}" in TOBE_MERMAID_USER


class TestHumanRolePrompts:
    def test_human_role_system_non_empty(self):
        assert len(HUMAN_ROLE_SYSTEM) > 50
        assert "JSON" in HUMAN_ROLE_SYSTEM

    def test_human_role_user_has_placeholders(self):
        assert "{title}" in HUMAN_ROLE_USER
        assert "{tobe_summary}" in HUMAN_ROLE_USER
        assert "{tobe_steps_json}" in HUMAN_ROLE_USER
        assert "{asis_roles_json}" in HUMAN_ROLE_USER
        assert "{selected_points_json}" in HUMAN_ROLE_USER

    def test_human_role_user_describes_levels(self):
        assert "H0" in HUMAN_ROLE_USER
        assert "H1" in HUMAN_ROLE_USER
        assert "H2" in HUMAN_ROLE_USER
        assert "H3" in HUMAN_ROLE_USER

    def test_human_role_user_describes_schema(self):
        assert "role_name" in HUMAN_ROLE_USER
        assert "mission" in HUMAN_ROLE_USER
        assert "responsibilities" in HUMAN_ROLE_USER
        assert "kpis" in HUMAN_ROLE_USER
        assert "boundaries" in HUMAN_ROLE_USER
