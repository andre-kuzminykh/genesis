"""Tests for TO-BE design service — covers FR-9, NFR-8, NFR-9.

Requirements tested:
  FR-9: TO-BE must be rebuilt based only on SELECTED automation points.
  NFR-8: TO-BE must maintain logical coherence with AS-IS.
  NFR-9: Output must be understandable by both business and IT.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.process_analyzer.schemas.models import (
    ASISModel,
    AutomationPoint,
    TOBEModel,
)
from src.process_analyzer.services.tobe_design import generate_tobe


@pytest.fixture
def mock_tobe_json_response():
    return {
        "summary": "Automated invoice processing with AI verification and RPA entry.",
        "steps": [
            {
                "id": "step_1",
                "name": "Автоприём счёта",
                "description": "Email parser извлекает данные",
                "actor": "System",
                "systems": ["Email Parser"],
            },
            {
                "id": "step_2",
                "name": "AI-сверка",
                "description": "AI проверяет реквизиты",
                "actor": "AI",
                "systems": ["AI Verification"],
            },
            {
                "id": "step_3",
                "name": "Контроль исключений",
                "description": "Бухгалтер проверяет отклонения",
                "actor": "Бухгалтер",
                "systems": ["Dashboard"],
            },
        ],
        "assumptions": ["OCR точен для стандартных форм"],
        "changes_rationale": [
            "Парсинг email заменяет ручной разбор (ap_1)",
            "AI-сверка заменяет ручную проверку (ap_2)",
        ],
    }


@pytest.fixture
def mock_tobe_mermaid():
    return "sequenceDiagram\n  System->>AI: Verify\n  AI->>Бухгалтер: Exceptions"


class TestGenerateTOBE:
    """FR-9, NFR-8: TO-BE generation based on selected automation points."""

    @pytest.mark.asyncio
    async def test_generates_valid_tobe_model(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        mock_tobe_json_response: dict,
        mock_tobe_mermaid: str,
    ):
        selected = [p for p in sample_automation_points if p.default_selected]

        with patch(
            "src.process_analyzer.services.tobe_design.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_tobe_json_response,
        ), patch(
            "src.process_analyzer.services.tobe_design.chat_completion",
            new_callable=AsyncMock,
            return_value=mock_tobe_mermaid,
        ):
            result = await generate_tobe("Test", sample_asis, selected)

        assert isinstance(result, TOBEModel)
        assert result.summary
        assert len(result.steps) >= 1
        assert result.mermaid_code

    @pytest.mark.asyncio
    async def test_tobe_includes_automated_actors(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        mock_tobe_json_response: dict,
        mock_tobe_mermaid: str,
    ):
        """NFR-8: TO-BE must include automated actors for selected points."""
        selected = [p for p in sample_automation_points if p.default_selected]

        with patch(
            "src.process_analyzer.services.tobe_design.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_tobe_json_response,
        ), patch(
            "src.process_analyzer.services.tobe_design.chat_completion",
            new_callable=AsyncMock,
            return_value=mock_tobe_mermaid,
        ):
            result = await generate_tobe("Test", sample_asis, selected)

        actors = {s.actor for s in result.steps}
        assert actors & {"System", "AI", "RPA Bot"}, (
            "TO-BE should have automated actors"
        )

    @pytest.mark.asyncio
    async def test_tobe_retains_human_steps(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        mock_tobe_json_response: dict,
        mock_tobe_mermaid: str,
    ):
        """NFR-8: Human oversight steps should remain in TO-BE."""
        selected = [p for p in sample_automation_points if p.default_selected]

        with patch(
            "src.process_analyzer.services.tobe_design.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_tobe_json_response,
        ), patch(
            "src.process_analyzer.services.tobe_design.chat_completion",
            new_callable=AsyncMock,
            return_value=mock_tobe_mermaid,
        ):
            result = await generate_tobe("Test", sample_asis, selected)

        human_steps = [
            s for s in result.steps
            if s.actor not in ("System", "AI", "RPA Bot")
        ]
        assert len(human_steps) >= 1, "TO-BE must retain human oversight steps"

    @pytest.mark.asyncio
    async def test_prompt_includes_selected_points_only(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        mock_tobe_json_response: dict,
        mock_tobe_mermaid: str,
    ):
        """FR-9: Only selected automation points sent to LLM."""
        selected = [sample_automation_points[0]]  # only ap_1

        with patch(
            "src.process_analyzer.services.tobe_design.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_tobe_json_response,
        ) as mock_json, patch(
            "src.process_analyzer.services.tobe_design.chat_completion",
            new_callable=AsyncMock,
            return_value=mock_tobe_mermaid,
        ):
            await generate_tobe("Test", sample_asis, selected)

        user_prompt = mock_json.call_args[0][1]
        assert "ap_1" in user_prompt
        assert "ap_4" not in user_prompt  # ap_4 was not selected

    @pytest.mark.asyncio
    async def test_tobe_has_rationale(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        mock_tobe_json_response: dict,
        mock_tobe_mermaid: str,
    ):
        """NFR-9: TO-BE must explain changes."""
        selected = sample_automation_points[:2]

        with patch(
            "src.process_analyzer.services.tobe_design.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_tobe_json_response,
        ), patch(
            "src.process_analyzer.services.tobe_design.chat_completion",
            new_callable=AsyncMock,
            return_value=mock_tobe_mermaid,
        ):
            result = await generate_tobe("Test", sample_asis, selected)

        assert len(result.changes_rationale) >= 1
        assert len(result.assumptions) >= 1

    @pytest.mark.asyncio
    async def test_tobe_generates_mermaid_diagram(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        mock_tobe_json_response: dict,
        mock_tobe_mermaid: str,
    ):
        selected = sample_automation_points[:2]

        with patch(
            "src.process_analyzer.services.tobe_design.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_tobe_json_response,
        ), patch(
            "src.process_analyzer.services.tobe_design.chat_completion",
            new_callable=AsyncMock,
            return_value=mock_tobe_mermaid,
        ):
            result = await generate_tobe("Test", sample_asis, selected)

        assert "sequenceDiagram" in result.mermaid_code

    @pytest.mark.asyncio
    async def test_prompt_includes_asis_context(
        self,
        sample_asis: ASISModel,
        sample_automation_points: list[AutomationPoint],
        mock_tobe_json_response: dict,
        mock_tobe_mermaid: str,
    ):
        """NFR-8: TO-BE prompt must reference AS-IS for coherence."""
        selected = sample_automation_points[:1]

        with patch(
            "src.process_analyzer.services.tobe_design.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_tobe_json_response,
        ) as mock_json, patch(
            "src.process_analyzer.services.tobe_design.chat_completion",
            new_callable=AsyncMock,
            return_value=mock_tobe_mermaid,
        ):
            await generate_tobe("Test", sample_asis, selected)

        user_prompt = mock_json.call_args[0][1]
        assert sample_asis.summary in user_prompt
