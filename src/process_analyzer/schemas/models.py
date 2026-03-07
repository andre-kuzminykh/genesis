from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AutomationType(str, Enum):
    DETERMINISTIC = "deterministic"
    INTELLIGENT = "intelligent"
    HYBRID = "hybrid"


class AutomationMaturity(str, Enum):
    QUICK_WIN = "quick_win"
    SHORT_TERM = "short_term"
    STRATEGIC = "strategic"


class HumanRoleLevel(str, Enum):
    H0_OPERATOR = "H0"
    H1_SUPERVISOR = "H1"
    H2_MANAGER = "H2"
    H3_EXPERT = "H3"


class ProcessStep(BaseModel):
    id: str
    name: str
    description: str
    actor: str
    systems: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    is_decision: bool = False
    pain_points: list[str] = Field(default_factory=list)


class Role(BaseModel):
    name: str
    description: str
    responsibilities: list[str] = Field(default_factory=list)


class ASISModel(BaseModel):
    summary: str
    roles: list[Role] = Field(default_factory=list)
    steps: list[ProcessStep] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    systems: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    mermaid_code: str = ""


class AutomationPoint(BaseModel):
    id: str
    step_id: str
    stage: str
    manual_action: str
    potential: str
    automation_type: AutomationType
    effect: str
    maturity: AutomationMaturity
    default_selected: bool = True


class TOBEModel(BaseModel):
    summary: str
    steps: list[ProcessStep] = Field(default_factory=list)
    mermaid_code: str = ""
    assumptions: list[str] = Field(default_factory=list)
    changes_rationale: list[str] = Field(default_factory=list)


class HumanRoleProfile(BaseModel):
    role_name: str
    level: HumanRoleLevel
    mission: str
    responsibilities: list[str] = Field(default_factory=list)
    boundaries: str = ""
    interactions: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    kpis: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


class SessionState(str, Enum):
    INPUT = "input"
    TRANSCRIBED = "transcribed"
    ASIS_GENERATED = "asis_generated"
    AUTOMATION_DIAGNOSED = "automation_diagnosed"
    TOBE_GENERATED = "tobe_generated"
    HTML_READY = "html_ready"


class SessionData(BaseModel):
    state: SessionState = SessionState.INPUT
    process_title: str = ""
    input_type: str = "text"
    raw_text: str = ""
    transcript: Optional[str] = None
    normalized_text: str = ""
    asis: Optional[ASISModel] = None
    automation_points: list[AutomationPoint] = Field(default_factory=list)
    selected_point_ids: list[str] = Field(default_factory=list)
    tobe: Optional[TOBEModel] = None
    human_role: Optional[HumanRoleProfile] = None
    html_report: str = ""
