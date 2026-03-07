from __future__ import annotations

import json
import logging

from src.process_analyzer.prompts.templates import (
    ASIS_MERMAID_SYSTEM,
    ASIS_MERMAID_USER,
    ASIS_SYSTEM,
    ASIS_USER,
)
from src.process_analyzer.schemas.models import ASISModel
from src.process_analyzer.services.llm_client import (
    chat_completion,
    chat_completion_json,
)

logger = logging.getLogger(__name__)


async def generate_asis(title: str, text: str) -> ASISModel:
    prompt = ASIS_USER.format(title=title, text=text)
    raw = await chat_completion_json(ASIS_SYSTEM, prompt)
    model = ASISModel(**raw)

    mermaid = await _generate_mermaid(title, model)
    model.mermaid_code = mermaid
    return model


async def _generate_mermaid(title: str, asis: ASISModel) -> str:
    steps_json = json.dumps(
        [s.model_dump() for s in asis.steps], ensure_ascii=False, indent=2
    )
    roles_json = json.dumps(
        [r.model_dump() for r in asis.roles], ensure_ascii=False, indent=2
    )
    prompt = ASIS_MERMAID_USER.format(
        title=title, steps_json=steps_json, roles_json=roles_json
    )
    return await chat_completion(ASIS_MERMAID_SYSTEM, prompt)
