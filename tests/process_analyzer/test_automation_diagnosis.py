"""Tests for automation diagnosis service — covers FR-6, FR-7, FR-8, NFR-6, NFR-7.

Requirements tested:
  FR-6: System must automatically identify automation points from AS-IS.
  FR-7: Each point must have: stage, manual_action, potential, automation_type, effect, maturity.
  FR-8: System must allow include/exclude each point before TO-BE generation.
  NFR-7: Automation point descriptions must be business-ready.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.process_analyzer.schemas.models import (
    ASISModel,
    AutomationMaturity,
    AutomationPoint,
    AutomationType,
)
from src.process_analyzer.services.automation_diagnosis import diagnose_automation


@pytest.fixture
def mock_diagnosis_response():
    """Realistic automation diagnosis LLM response."""
    return [
        {
            "id": "ap_1",
            "step_id": "step_1",
            "stage": "Получение счёта",
            "manual_action": "Ручной разбор email",
            "potential": "Автоматический парсинг входящих писем",
            "automation_type": "deterministic",
            "effect": "Сокращение времени на 80%",
            "maturity": "quick_win",
            "default_selected": True,
        },
        {
            "id": "ap_2",
            "step_id": "step_2",
            "stage": "Сверка реквизитов",
            "manual_action": "Ручная сверка",
            "potential": "AI-сверка документов",
            "automation_type": "intelligent",
            "effect": "Снижение ошибок на 90%",
            "maturity": "short_term",
            "default_selected": True,
        },
        {
            "id": "ap_3",
            "step_id": "step_3",
            "stage": "Ввод данных",
            "manual_action": "Ручной ввод",
            "potential": "RPA автозаполнение",
            "automation_type": "deterministic",
            "effect": "Экономия 30 мин",
            "maturity": "quick_win",
            "default_selected": True,
        },
        {
            "id": "ap_4",
            "step_id": "step_4",
            "stage": "Согласование",
            "manual_action": "Маршрутизация на подпись",
            "potential": "Workflow автоматизация",
            "automation_type": "hybrid",
            "effect": "Ускорение в 3 раза",
            "maturity": "strategic",
            "default_selected": False,
        },
    ]


class TestDiagnoseAutomation:
    """FR-6, FR-7: Automation point extraction and classification."""

    @pytest.mark.asyncio
    async def test_returns_list_of_automation_points(
        self, sample_asis: ASISModel, mock_diagnosis_response: list
    ):
        """FR-6: Returns structured list from AS-IS."""
        with patch(
            "src.process_analyzer.services.automation_diagnosis.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_diagnosis_response,
        ):
            points = await diagnose_automation("Test", sample_asis)

        assert isinstance(points, list)
        assert len(points) == 4
        assert all(isinstance(p, AutomationPoint) for p in points)

    @pytest.mark.asyncio
    async def test_each_point_has_required_fields(
        self, sample_asis: ASISModel, mock_diagnosis_response: list
    ):
        """FR-7: Each point must have stage, manual_action, potential, type, effect, maturity."""
        with patch(
            "src.process_analyzer.services.automation_diagnosis.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_diagnosis_response,
        ):
            points = await diagnose_automation("Test", sample_asis)

        for point in points:
            assert point.id, "id is required"
            assert point.step_id, "step_id is required"
            assert point.stage, "stage is required"
            assert point.manual_action, "manual_action is required"
            assert point.potential, "potential is required"
            assert point.automation_type in AutomationType
            assert point.effect, "effect is required"
            assert point.maturity in AutomationMaturity

    @pytest.mark.asyncio
    async def test_automation_types_classified_correctly(
        self, sample_asis: ASISModel, mock_diagnosis_response: list
    ):
        """FR-7: Correct automation type classification."""
        with patch(
            "src.process_analyzer.services.automation_diagnosis.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_diagnosis_response,
        ):
            points = await diagnose_automation("Test", sample_asis)

        types = {p.id: p.automation_type for p in points}
        assert types["ap_1"] == AutomationType.DETERMINISTIC
        assert types["ap_2"] == AutomationType.INTELLIGENT
        assert types["ap_4"] == AutomationType.HYBRID

    @pytest.mark.asyncio
    async def test_maturity_levels_assigned(
        self, sample_asis: ASISModel, mock_diagnosis_response: list
    ):
        """FR-7: Maturity levels correctly assigned."""
        with patch(
            "src.process_analyzer.services.automation_diagnosis.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_diagnosis_response,
        ):
            points = await diagnose_automation("Test", sample_asis)

        maturities = {p.id: p.maturity for p in points}
        assert maturities["ap_1"] == AutomationMaturity.QUICK_WIN
        assert maturities["ap_2"] == AutomationMaturity.SHORT_TERM
        assert maturities["ap_4"] == AutomationMaturity.STRATEGIC

    @pytest.mark.asyncio
    async def test_default_selection_applied(
        self, sample_asis: ASISModel, mock_diagnosis_response: list
    ):
        """FR-8: Points have default selection state for user interaction."""
        with patch(
            "src.process_analyzer.services.automation_diagnosis.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_diagnosis_response,
        ):
            points = await diagnose_automation("Test", sample_asis)

        selected = [p for p in points if p.default_selected]
        unselected = [p for p in points if not p.default_selected]
        assert len(selected) == 3
        assert len(unselected) == 1
        assert unselected[0].maturity == AutomationMaturity.STRATEGIC

    @pytest.mark.asyncio
    async def test_prompt_includes_asis_data(
        self, sample_asis: ASISModel, mock_diagnosis_response: list
    ):
        """Verify the prompt sent to LLM contains AS-IS information."""
        with patch(
            "src.process_analyzer.services.automation_diagnosis.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_diagnosis_response,
        ) as mock_json:
            await diagnose_automation("Invoice Process", sample_asis)

        user_prompt = mock_json.call_args[0][1]
        assert "Invoice Process" in user_prompt
        assert sample_asis.summary in user_prompt

    @pytest.mark.asyncio
    async def test_empty_diagnosis_returns_empty_list(self, sample_asis: ASISModel):
        """Edge case: LLM returns no automation points."""
        with patch(
            "src.process_analyzer.services.automation_diagnosis.chat_completion_json",
            new_callable=AsyncMock,
            return_value=[],
        ):
            points = await diagnose_automation("Test", sample_asis)

        assert points == []
