"""Tests for HTML report builder — covers FR-11, FR-12, NFR-10, NFR-11.

Requirements tested:
  FR-11: HTML page must have sections: AS-IS, automation points, TO-BE, new human role.
  FR-12: System must support preview and download of HTML file.
  NFR-10: HTML must be portable — open locally without backend.
  NFR-11: Visual presentation must be readable on desktop.
"""

from __future__ import annotations

import pytest

from src.process_analyzer.schemas.models import (
    ASISModel,
    AutomationPoint,
    HumanRoleProfile,
    TOBEModel,
)
from src.process_analyzer.services.html_report import build_html_report


class TestHTMLReportBuilder:
    """FR-11, NFR-10, NFR-11: HTML report generation."""

    def test_generates_html_string(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        html = build_html_report(
            title="Invoice Process",
            transcript="Some transcript text",
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=["ap_1", "ap_2"],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        assert isinstance(html, str)
        assert len(html) > 100
        assert html.strip().startswith("<!DOCTYPE html>")

    def test_contains_asis_section(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        """FR-11: Must have AS-IS section."""
        html = build_html_report(
            title="Test",
            transcript=None,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=["ap_1"],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        assert 'id="asis"' in html
        assert "AS-IS" in html
        assert sample_asis.summary in html

    def test_contains_automation_points_section(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        """FR-11: Must have automation points section."""
        html = build_html_report(
            title="Test",
            transcript=None,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=["ap_1", "ap_3"],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        assert 'id="automation"' in html
        assert "Automation" in html

    def test_contains_tobe_section(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        """FR-11: Must have TO-BE section."""
        html = build_html_report(
            title="Test",
            transcript=None,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=["ap_1"],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        assert 'id="tobe"' in html
        assert "TO-BE" in html
        assert sample_tobe.summary in html

    def test_contains_human_role_section(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        """FR-11: Must have new human role section."""
        html = build_html_report(
            title="Test",
            transcript=None,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=["ap_1"],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        assert 'id="role"' in html
        assert sample_human_role.role_name in html
        assert sample_human_role.mission in html

    def test_contains_transcript_when_provided(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        transcript = "Это текст транскрипции интервью с бухгалтером."
        html = build_html_report(
            title="Test",
            transcript=transcript,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=[],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        assert 'id="input"' in html
        assert transcript in html

    def test_no_transcript_section_when_none(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        html = build_html_report(
            title="Test",
            transcript=None,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=[],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        assert 'id="input"' not in html

    def test_selected_vs_unselected_badges(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        """FR-8/FR-11: Selected/unselected status visible in report."""
        html = build_html_report(
            title="Test",
            transcript=None,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=["ap_1", "ap_2"],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        assert "Selected" in html
        assert "Skipped" in html

    def test_html_is_self_contained(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        """NFR-10: HTML must be portable — includes inline styles and CDN scripts."""
        html = build_html_report(
            title="Test",
            transcript=None,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=[],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        assert "<style>" in html
        assert "mermaid" in html.lower()
        assert "</html>" in html

    def test_contains_mermaid_diagrams(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        """NFR-11: Must render Mermaid diagrams."""
        html = build_html_report(
            title="Test",
            transcript=None,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=[],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        assert 'class="mermaid"' in html
        assert "mermaid.initialize" in html

    def test_title_in_report(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        html = build_html_report(
            title="Invoice Approval Flow",
            transcript=None,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=[],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        assert "Invoice Approval Flow" in html

    def test_all_asis_steps_in_report(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        html = build_html_report(
            title="Test",
            transcript=None,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=[],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        for step in sample_asis.steps:
            assert step.name in html

    def test_all_tobe_steps_in_report(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        html = build_html_report(
            title="Test",
            transcript=None,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=[],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        for step in sample_tobe.steps:
            assert step.name in html

    def test_human_role_kpis_in_report(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        html = build_html_report(
            title="Test",
            transcript=None,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=[],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        for kpi in sample_human_role.kpis:
            assert kpi in html

    def test_role_level_displayed(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        html = build_html_report(
            title="Test",
            transcript=None,
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=[],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        assert sample_human_role.level.value in html

    def test_navigation_links(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        sample_tobe: TOBEModel,
        sample_human_role: HumanRoleProfile,
    ):
        """NFR-11: Navigable sections."""
        html = build_html_report(
            title="Test",
            transcript="text",
            asis=sample_asis,
            automation_points=sample_automation_points,
            selected_ids=[],
            tobe=sample_tobe,
            human_role=sample_human_role,
        )

        assert 'href="#asis"' in html
        assert 'href="#automation"' in html
        assert 'href="#tobe"' in html
        assert 'href="#role"' in html
