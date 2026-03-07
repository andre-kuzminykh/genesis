from __future__ import annotations

import json
import logging

from src.process_analyzer.prompts.templates import HUMAN_ROLE_SYSTEM, HUMAN_ROLE_USER
from src.process_analyzer.schemas.models import (
    ASISModel,
    AutomationPoint,
    HumanRoleProfile,
    TOBEModel,
)
from src.process_analyzer.services.llm_client import chat_completion_json

logger = logging.getLogger(__name__)


async def generate_human_role(
    title: str,
    asis: ASISModel,
    tobe: TOBEModel,
    selected_points: list[AutomationPoint],
) -> HumanRoleProfile:
    tobe_steps_json = json.dumps(
        [s.model_dump() for s in tobe.steps], ensure_ascii=False, indent=2
    )
    asis_roles_json = json.dumps(
        [r.model_dump() for r in asis.roles], ensure_ascii=False, indent=2
    )
    selected_points_json = json.dumps(
        [p.model_dump() for p in selected_points], ensure_ascii=False, indent=2
    )

    prompt = HUMAN_ROLE_USER.format(
        title=title,
        tobe_summary=tobe.summary,
        tobe_steps_json=tobe_steps_json,
        asis_roles_json=asis_roles_json,
        selected_points_json=selected_points_json,
    )

    raw = await chat_completion_json(HUMAN_ROLE_SYSTEM, prompt)
    return HumanRoleProfile(**raw)
