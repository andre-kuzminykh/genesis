from __future__ import annotations

import json
import logging

from src.process_analyzer.prompts.templates import (
    ASIS_MERMAID_SYSTEM,
    TOBE_MERMAID_USER,
    TOBE_SYSTEM,
    TOBE_USER,
)
from src.process_analyzer.schemas.models import (
    ASISModel,
    AutomationPoint,
    TOBEModel,
)
from src.process_analyzer.services.llm_client import (
    chat_completion,
    chat_completion_json,
)

logger = logging.getLogger(__name__)


async def generate_tobe(
    title: str,
    asis: ASISModel,
    selected_points: list[AutomationPoint],
) -> TOBEModel:
    asis_steps_json = json.dumps(
        [s.model_dump() for s in asis.steps], ensure_ascii=False, indent=2
    )
    selected_points_json = json.dumps(
        [p.model_dump() for p in selected_points], ensure_ascii=False, indent=2
    )

    prompt = TOBE_USER.format(
        title=title,
        asis_summary=asis.summary,
        asis_steps_json=asis_steps_json,
        selected_points_json=selected_points_json,
    )

    raw = await chat_completion_json(TOBE_SYSTEM, prompt)
    model = TOBEModel(**raw)

    mermaid = await _generate_tobe_mermaid(title, model)
    model.mermaid_code = mermaid
    return model


async def _generate_tobe_mermaid(title: str, tobe: TOBEModel) -> str:
    steps_json = json.dumps(
        [s.model_dump() for s in tobe.steps], ensure_ascii=False, indent=2
    )
    prompt = TOBE_MERMAID_USER.format(title=title, steps_json=steps_json)
    return await chat_completion(ASIS_MERMAID_SYSTEM, prompt)
