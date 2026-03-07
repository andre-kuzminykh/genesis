"""Shared fixtures for process_analyzer tests."""

from __future__ import annotations

import pytest

from src.process_analyzer.schemas.models import (
    ASISModel,
    AutomationMaturity,
    AutomationPoint,
    AutomationType,
    HumanRoleLevel,
    HumanRoleProfile,
    ProcessStep,
    Role,
    TOBEModel,
)


@pytest.fixture
def sample_process_text() -> str:
    """Realistic interview transcript for testing (~2000 chars)."""
    return (
        "Сейчас процесс согласования счетов у нас выглядит так. "
        "Бухгалтер получает счёт от поставщика по email. Он проверяет реквизиты вручную, "
        "сверяет с договором в папке на сервере. Если всё ок, бухгалтер вводит данные "
        "в 1С, формирует платёжное поручение и отправляет его на подпись финансовому "
        "директору. Финансовый директор просматривает документ, может запросить "
        "дополнительную информацию у бухгалтера по телефону. Если одобряет — подписывает "
        "в системе Банк-Клиент. Потом бухгалтер проверяет статус оплаты, обновляет "
        "данные в 1С и архивирует документы. Проблемы: ручная сверка занимает много "
        "времени, часто теряются письма, финдир долго ждёт бумаги, нет единого реестра "
        "статусов оплат."
    )


@pytest.fixture
def sample_asis() -> ASISModel:
    return ASISModel(
        summary="Invoice approval process with manual checks and multiple handoffs.",
        roles=[
            Role(
                name="Бухгалтер",
                description="Обрабатывает входящие счета",
                responsibilities=["Проверка реквизитов", "Ввод в 1С", "Архивация"],
            ),
            Role(
                name="Финансовый директор",
                description="Согласует оплаты",
                responsibilities=["Проверка и подпись платёжек"],
            ),
        ],
        steps=[
            ProcessStep(
                id="step_1",
                name="Получение счёта",
                description="Бухгалтер получает счёт по email",
                actor="Бухгалтер",
                systems=["Email"],
                inputs=["Счёт от поставщика"],
                outputs=["Входящий счёт"],
                pain_points=["Письма теряются"],
            ),
            ProcessStep(
                id="step_2",
                name="Сверка реквизитов",
                description="Ручная проверка реквизитов с договором",
                actor="Бухгалтер",
                systems=["Файловый сервер"],
                inputs=["Счёт", "Договор"],
                outputs=["Подтверждённый счёт"],
                pain_points=["Занимает много времени"],
            ),
            ProcessStep(
                id="step_3",
                name="Ввод в 1С",
                description="Ручной ввод данных счёта в 1С",
                actor="Бухгалтер",
                systems=["1С"],
                inputs=["Подтверждённый счёт"],
                outputs=["Запись в 1С"],
            ),
            ProcessStep(
                id="step_4",
                name="Согласование",
                description="Финансовый директор проверяет и подписывает",
                actor="Финансовый директор",
                systems=["Банк-Клиент"],
                inputs=["Платёжное поручение"],
                outputs=["Подписанный документ"],
                is_decision=True,
                pain_points=["Долгое ожидание"],
            ),
        ],
        artifacts=["Счёт", "Договор", "Платёжное поручение"],
        systems=["Email", "1С", "Банк-Клиент", "Файловый сервер"],
        metrics=["Время обработки счёта"],
        issues=["Ручная сверка", "Потеря писем", "Нет единого реестра"],
        mermaid_code="sequenceDiagram\n  Бухгалтер->>1С: Ввод данных",
    )


@pytest.fixture
def sample_automation_points() -> list[AutomationPoint]:
    return [
        AutomationPoint(
            id="ap_1",
            step_id="step_1",
            stage="Получение счёта",
            manual_action="Ручной разбор email",
            potential="Автоматический парсинг входящих писем со счетами",
            automation_type=AutomationType.DETERMINISTIC,
            effect="Сокращение времени на 80%",
            maturity=AutomationMaturity.QUICK_WIN,
            default_selected=True,
        ),
        AutomationPoint(
            id="ap_2",
            step_id="step_2",
            stage="Сверка реквизитов",
            manual_action="Ручная сверка с договором",
            potential="AI-сверка документов",
            automation_type=AutomationType.INTELLIGENT,
            effect="Снижение ошибок на 90%",
            maturity=AutomationMaturity.SHORT_TERM,
            default_selected=True,
        ),
        AutomationPoint(
            id="ap_3",
            step_id="step_3",
            stage="Ввод в 1С",
            manual_action="Ручной ввод данных",
            potential="RPA бот для автоматического заполнения",
            automation_type=AutomationType.DETERMINISTIC,
            effect="Экономия 30 мин на счёт",
            maturity=AutomationMaturity.QUICK_WIN,
            default_selected=True,
        ),
        AutomationPoint(
            id="ap_4",
            step_id="step_4",
            stage="Согласование",
            manual_action="Ручная маршрутизация на подпись",
            potential="Workflow engine с автоматической маршрутизацией",
            automation_type=AutomationType.HYBRID,
            effect="Ускорение согласования в 3 раза",
            maturity=AutomationMaturity.STRATEGIC,
            default_selected=False,
        ),
    ]


@pytest.fixture
def sample_tobe() -> TOBEModel:
    return TOBEModel(
        summary="Automated invoice processing with AI verification and RPA data entry.",
        steps=[
            ProcessStep(
                id="step_1",
                name="Автоматический приём счёта",
                description="Система парсит email и извлекает данные",
                actor="System",
                systems=["Email Parser", "OCR"],
            ),
            ProcessStep(
                id="step_2",
                name="AI-сверка",
                description="AI проверяет реквизиты с договорной базой",
                actor="AI",
                systems=["AI Verification", "Contract DB"],
            ),
            ProcessStep(
                id="step_3",
                name="Автоввод в 1С",
                description="RPA бот заполняет данные в 1С",
                actor="RPA Bot",
                systems=["1С", "RPA Platform"],
            ),
            ProcessStep(
                id="step_4",
                name="Контроль и эскалации",
                description="Бухгалтер проверяет отклонения и исключения",
                actor="Бухгалтер",
                systems=["Dashboard"],
            ),
        ],
        mermaid_code="sequenceDiagram\n  System->>AI: Verify\n  AI->>RPA: Enter",
        assumptions=["OCR достаточно точен для стандартных счетов"],
        changes_rationale=["Автоматизация парсинга email экономит 80% времени"],
    )


@pytest.fixture
def sample_human_role() -> HumanRoleProfile:
    return HumanRoleProfile(
        role_name="Контролёр счетов",
        level=HumanRoleLevel.H1_SUPERVISOR,
        mission="Контролировать качество автоматической обработки счетов",
        responsibilities=[
            "Мониторинг автоматических процессов",
            "Обработка исключений и отклонений",
            "Валидация результатов AI-сверки",
        ],
        boundaries="Не выполняет ручной ввод данных, не ищет счета в email",
        interactions=["AI-система сверки", "RPA платформа", "Финансовый директор"],
        outputs=["Отчёт по исключениям", "Подтверждение корректности"],
        kpis=["% автоматически обработанных счетов", "Время реакции на исключение"],
        tools=["Dashboard мониторинга", "1С", "AI Verification"],
    )
