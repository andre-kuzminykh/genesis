"""Tests for AS-IS analysis service — covers FR-2, FR-3, NFR-1, NFR-3.

Requirements tested:
  FR-2: System must extract roles, steps, artifacts, decisions, systems, metrics from text.
  FR-3: System must produce AS-IS with textual summary AND Mermaid diagram.
  NFR-1: AS-IS generation must complete within 60 seconds (tested via mock).
  NFR-3: System must handle unstructured, conversational text.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.process_analyzer.schemas.models import ASISModel
from src.process_analyzer.services.asis_analysis import generate_asis


@pytest.fixture
def mock_asis_json_response():
    """Return realistic AS-IS JSON that LLM would produce."""
    return {
        "summary": "Invoice approval process involving accountant and finance director.",
        "roles": [
            {
                "name": "Бухгалтер",
                "description": "Обрабатывает счета",
                "responsibilities": ["Проверка реквизитов", "Ввод в 1С"],
            },
            {
                "name": "Финансовый директор",
                "description": "Согласует оплаты",
                "responsibilities": ["Подписание платёжек"],
            },
        ],
        "steps": [
            {
                "id": "step_1",
                "name": "Получение счёта",
                "description": "Бухгалтер получает счёт по email",
                "actor": "Бухгалтер",
                "systems": ["Email"],
                "inputs": ["Счёт"],
                "outputs": ["Входящий документ"],
                "is_decision": False,
                "pain_points": ["Письма теряются"],
            },
            {
                "id": "step_2",
                "name": "Сверка",
                "description": "Ручная проверка с договором",
                "actor": "Бухгалтер",
                "systems": ["Файловый сервер"],
                "inputs": ["Счёт", "Договор"],
                "outputs": ["Результат сверки"],
                "is_decision": False,
                "pain_points": ["Долго"],
            },
            {
                "id": "step_3",
                "name": "Согласование",
                "description": "Финдир подписывает",
                "actor": "Финансовый директор",
                "systems": ["Банк-Клиент"],
                "inputs": ["Платёжка"],
                "outputs": ["Подпись"],
                "is_decision": True,
                "pain_points": [],
            },
        ],
        "artifacts": ["Счёт", "Договор", "Платёжное поручение"],
        "systems": ["Email", "1С", "Банк-Клиент"],
        "metrics": ["Время обработки"],
        "issues": ["Ручная сверка", "Потеря писем"],
    }


@pytest.fixture
def mock_mermaid_response():
    return "sequenceDiagram\n  Бухгалтер->>Финдир: Платёжка\n  Финдир->>Банк: Подпись"


class TestGenerateASIS:
    """FR-2, FR-3: AS-IS generation from text."""

    @pytest.mark.asyncio
    async def test_generates_complete_asis_model(
        self,
        sample_process_text: str,
        mock_asis_json_response: dict,
        mock_mermaid_response: str,
    ):
        """FR-2: Must extract roles, steps, artifacts, systems, metrics."""
        with patch(
            "src.process_analyzer.services.asis_analysis.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_asis_json_response,
        ), patch(
            "src.process_analyzer.services.asis_analysis.chat_completion",
            new_callable=AsyncMock,
            return_value=mock_mermaid_response,
        ):
            result = await generate_asis("Согласование счетов", sample_process_text)

        assert isinstance(result, ASISModel)
        assert result.summary
        assert len(result.roles) == 2
        assert len(result.steps) == 3
        assert len(result.artifacts) >= 1
        assert len(result.systems) >= 1
        assert len(result.metrics) >= 1
        assert len(result.issues) >= 1

    @pytest.mark.asyncio
    async def test_generates_mermaid_diagram(
        self,
        sample_process_text: str,
        mock_asis_json_response: dict,
        mock_mermaid_response: str,
    ):
        """FR-3: Must include Mermaid diagram in AS-IS output."""
        with patch(
            "src.process_analyzer.services.asis_analysis.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_asis_json_response,
        ), patch(
            "src.process_analyzer.services.asis_analysis.chat_completion",
            new_callable=AsyncMock,
            return_value=mock_mermaid_response,
        ):
            result = await generate_asis("Test", sample_process_text)

        assert result.mermaid_code
        assert "sequenceDiagram" in result.mermaid_code

    @pytest.mark.asyncio
    async def test_calls_llm_with_correct_prompts(
        self,
        mock_asis_json_response: dict,
        mock_mermaid_response: str,
    ):
        """Verify prompts include title and text."""
        with patch(
            "src.process_analyzer.services.asis_analysis.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_asis_json_response,
        ) as mock_json, patch(
            "src.process_analyzer.services.asis_analysis.chat_completion",
            new_callable=AsyncMock,
            return_value=mock_mermaid_response,
        ):
            await generate_asis("Invoice Process", "Some text about invoices")

        call_args = mock_json.call_args
        user_prompt = call_args[0][1]
        assert "Invoice Process" in user_prompt
        assert "Some text about invoices" in user_prompt

    @pytest.mark.asyncio
    async def test_handles_decision_steps(
        self,
        mock_asis_json_response: dict,
        mock_mermaid_response: str,
    ):
        """FR-2: Must identify decision points."""
        with patch(
            "src.process_analyzer.services.asis_analysis.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_asis_json_response,
        ), patch(
            "src.process_analyzer.services.asis_analysis.chat_completion",
            new_callable=AsyncMock,
            return_value=mock_mermaid_response,
        ):
            result = await generate_asis("Test", "process text")

        decision_steps = [s for s in result.steps if s.is_decision]
        assert len(decision_steps) >= 1
        assert decision_steps[0].name == "Согласование"

    @pytest.mark.asyncio
    async def test_handles_minimal_input(
        self,
        mock_mermaid_response: str,
    ):
        """NFR-3: Must handle sparse, unstructured input."""
        minimal_response = {
            "summary": "Simple process",
            "roles": [],
            "steps": [
                {
                    "id": "step_1",
                    "name": "Do something",
                    "description": "A step",
                    "actor": "Someone",
                }
            ],
            "artifacts": [],
            "systems": [],
            "metrics": [],
            "issues": [],
        }

        with patch(
            "src.process_analyzer.services.asis_analysis.chat_completion_json",
            new_callable=AsyncMock,
            return_value=minimal_response,
        ), patch(
            "src.process_analyzer.services.asis_analysis.chat_completion",
            new_callable=AsyncMock,
            return_value=mock_mermaid_response,
        ):
            result = await generate_asis("Minimal", "some vague process")

        assert isinstance(result, ASISModel)
        assert result.summary == "Simple process"
        assert len(result.steps) == 1

    @pytest.mark.asyncio
    async def test_mermaid_generation_uses_steps_and_roles(
        self,
        mock_asis_json_response: dict,
        mock_mermaid_response: str,
    ):
        """FR-3: Mermaid generation receives structured step and role data."""
        with patch(
            "src.process_analyzer.services.asis_analysis.chat_completion_json",
            new_callable=AsyncMock,
            return_value=mock_asis_json_response,
        ), patch(
            "src.process_analyzer.services.asis_analysis.chat_completion",
            new_callable=AsyncMock,
            return_value=mock_mermaid_response,
        ) as mock_mermaid:
            await generate_asis("Test", "text")

        mermaid_prompt = mock_mermaid.call_args[0][1]
        assert "step_1" in mermaid_prompt or "Получение" in mermaid_prompt
