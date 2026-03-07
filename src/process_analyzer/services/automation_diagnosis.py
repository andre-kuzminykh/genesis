from __future__ import annotations

import json
import logging

from src.process_analyzer.prompts.templates import AUTOMATION_SYSTEM, AUTOMATION_USER
from src.process_analyzer.schemas.models import ASISModel, AutomationPoint
from src.process_analyzer.services.llm_client import chat_completion_json

logger = logging.getLogger(__name__)


async def diagnose_automation(
    title: str, asis: ASISModel
) -> list[AutomationPoint]:
    steps_json = json.dumps(
        [s.model_dump() for s in asis.steps], ensure_ascii=False, indent=2
    )
    prompt = AUTOMATION_USER.format(
        title=title,
        summary=asis.summary,
        steps_json=steps_json,
    )

    raw = await chat_completion_json(AUTOMATION_SYSTEM, prompt)

    points: list[AutomationPoint] = []
    for item in raw:
        points.append(AutomationPoint(**item))

    logger.info("Diagnosed %d automation points", len(points))
    return points
