"""Tests for human role redesign service — covers FR-10.

Requirements tested:
  FR-10: System must generate new human role showing shift from routine
         to control, escalation, improvement, and decision-making.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.process_analyzer.schemas.models import (
    ASISModel,
    AutomationPoint,
    HumanRoleLevel,
    HumanRoleProfile,
    TOBEModel,
)
from src.process_analyzer.services.human_role import generate_human_role


@pytest.fixture
def mock_human_role_response():
    return {
        "role_name": "Контролёр автоматической обработки счетов",
        "level": "H1",
        "mission": "Обеспечить качество автоматической обработки и оперативно решать исключения",
        "responsibilities": [
            "Мониторинг автоматических процессов",
            "Обработка исключений и отклонений",
            "Валидация критических AI-решений",
            "Эскалация сложных кейсов финансовому директору",
        ],
        "boundaries": "Не выполняет ручной ввод данных, не разбирает входящую почту, не сверяет реквизиты вручную",
        "interactions": [
            "AI-система верификации",
            "RPA платформа",
            "Финансовый директор",
            "Поставщики (при исключениях)",
        ],
        "outputs": [
            "Отчёт по исключениям",
            "Решения по нестандартным случаям",
            "Подтверждение корректности пакета документов",
        ],
        "kpis": [
            "% счетов, обработанных полностью автоматически",
            "Среднее время реакции на исключение",
            "Количество ошибок после автоматической обработки",
        ],
        "tools": ["Dashboard мониторинга", "1С", "AI Verification UI"],
    }


class TestGenerateHumanRole:
    """FR-10: Human role generation tests."""

    @pytest.mark.asyncio
    async def test_generates_valid_human_role(
        self,
        sample_asis: ASISModel,
        sample_tobe: TOBEModel,
        sample_automation_points: list[AutomationPoint],
        mock_human_role_response: dict,
    ):
        selected = [p for p in sample_automation_points if p.default_selected]

        with patch(
            "src.process_analyzer.services.human_role.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_human_role_response,
        ):
            result = await generate_human_role("Test", sample_asis, sample_tobe, selected)

        assert isinstance(result, HumanRoleProfile)
        assert result.role_name
        assert result.level == HumanRoleLevel.H1_SUPERVISOR
        assert result.mission

    @pytest.mark.asyncio
    async def test_role_has_supervision_responsibilities(
        self,
        sample_asis: ASISModel,
        sample_tobe: TOBEModel,
        sample_automation_points: list[AutomationPoint],
        mock_human_role_response: dict,
    ):
        """FR-10: Role must shift from routine to supervision."""
        selected = [p for p in sample_automation_points if p.default_selected]

        with patch(
            "src.process_analyzer.services.human_role.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_human_role_response,
        ):
            result = await generate_human_role("Test", sample_asis, sample_tobe, selected)

        resp_text = " ".join(result.responsibilities).lower()
        supervision_keywords = ["мониторинг", "исключен", "валидац", "эскалац", "контрол"]
        assert any(kw in resp_text for kw in supervision_keywords), (
            f"Role responsibilities must include supervision terms, got: {result.responsibilities}"
        )

    @pytest.mark.asyncio
    async def test_role_has_boundaries(
        self,
        sample_asis: ASISModel,
        sample_tobe: TOBEModel,
        sample_automation_points: list[AutomationPoint],
        mock_human_role_response: dict,
    ):
        """FR-10: Role must specify what is NOT done by human anymore."""
        selected = [p for p in sample_automation_points if p.default_selected]

        with patch(
            "src.process_analyzer.services.human_role.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_human_role_response,
        ):
            result = await generate_human_role("Test", sample_asis, sample_tobe, selected)

        assert result.boundaries
        assert "ручной" in result.boundaries.lower() or "не " in result.boundaries.lower()

    @pytest.mark.asyncio
    async def test_role_has_kpis(
        self,
        sample_asis: ASISModel,
        sample_tobe: TOBEModel,
        sample_automation_points: list[AutomationPoint],
        mock_human_role_response: dict,
    ):
        selected = [p for p in sample_automation_points if p.default_selected]

        with patch(
            "src.process_analyzer.services.human_role.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_human_role_response,
        ):
            result = await generate_human_role("Test", sample_asis, sample_tobe, selected)

        assert len(result.kpis) >= 1

    @pytest.mark.asyncio
    async def test_role_has_tools(
        self,
        sample_asis: ASISModel,
        sample_tobe: TOBEModel,
        sample_automation_points: list[AutomationPoint],
        mock_human_role_response: dict,
    ):
        selected = [p for p in sample_automation_points if p.default_selected]

        with patch(
            "src.process_analyzer.services.human_role.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_human_role_response,
        ):
            result = await generate_human_role("Test", sample_asis, sample_tobe, selected)

        assert len(result.tools) >= 1

    @pytest.mark.asyncio
    async def test_prompt_includes_tobe_and_asis_context(
        self,
        sample_asis: ASISModel,
        sample_tobe: TOBEModel,
        sample_automation_points: list[AutomationPoint],
        mock_human_role_response: dict,
    ):
        selected = sample_automation_points[:1]

        with patch(
            "src.process_analyzer.services.human_role.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_human_role_response,
        ) as mock_json:
            await generate_human_role("Invoice Process", sample_asis, sample_tobe, selected)

        user_prompt = mock_json.call_args[0][1]
        assert sample_tobe.summary in user_prompt
        assert "Invoice Process" in user_prompt
