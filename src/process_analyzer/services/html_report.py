from __future__ import annotations

import logging

from jinja2 import Environment, FileSystemLoader

from src.process_analyzer.config import TEMPLATES_DIR
from src.process_analyzer.schemas.models import (
    ASISModel,
    AutomationPoint,
    HumanRoleProfile,
    TOBEModel,
)

logger = logging.getLogger(__name__)

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
)


def build_html_report(
    title: str,
    transcript: str | None,
    asis: ASISModel,
    automation_points: list[AutomationPoint],
    selected_ids: list[str],
    tobe: TOBEModel,
    human_role: HumanRoleProfile,
) -> str:
    template = _env.get_template("report.html")
    html = template.render(
        title=title,
        transcript=transcript,
        asis=asis,
        automation_points=automation_points,
        selected_ids=set(selected_ids),
        tobe=tobe,
        human_role=human_role,
    )
    return html
