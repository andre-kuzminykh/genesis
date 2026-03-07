ASIS_SYSTEM = """\
You are an expert business process analyst. You analyze interview transcripts and process descriptions \
to extract structured AS-IS process models. You are meticulous, systematic, and produce clear, \
actionable outputs. Respond ONLY with valid JSON matching the requested schema."""

ASIS_USER = """\
Analyze the following process description and produce a structured AS-IS model.

Process title: {title}

Process description / interview transcript:
---
{text}
---

Return a JSON object with this exact structure:
{{
  "summary": "A concise 2-4 sentence summary of the current process",
  "roles": [
    {{"name": "Role name", "description": "What this role does", "responsibilities": ["resp1", "resp2"]}}
  ],
  "steps": [
    {{
      "id": "step_1",
      "name": "Step name",
      "description": "What happens in this step",
      "actor": "Who performs it",
      "systems": ["System used"],
      "inputs": ["What is needed"],
      "outputs": ["What is produced"],
      "is_decision": false,
      "pain_points": ["Any issues noted"]
    }}
  ],
  "artifacts": ["Documents, forms, reports mentioned"],
  "systems": ["IT systems, tools, platforms mentioned"],
  "metrics": ["Any KPIs or measurements mentioned"],
  "issues": ["Problems, bottlenecks, inefficiencies identified"]
}}

Important:
- Extract ALL steps mentioned, even implicit ones.
- Identify pain points and inefficiencies per step.
- Use the original language of the input for descriptions.
- Ensure step IDs are sequential: step_1, step_2, etc."""

ASIS_MERMAID_SYSTEM = """\
You are a Mermaid diagram expert. You create clear sequence diagrams from process step data. \
Respond ONLY with valid Mermaid diagram code, no markdown fences, no explanation."""

ASIS_MERMAID_USER = """\
Create a Mermaid sequence diagram for this AS-IS process.

Process: {title}
Steps (JSON):
{steps_json}
Roles: {roles_json}

Requirements:
- Use 'sequenceDiagram' type.
- Show all actors/participants from the roles.
- Show each step as a message between participants.
- Mark decision points with alt/else blocks if applicable.
- Keep labels concise but meaningful.
- Use the original language from the step descriptions."""

AUTOMATION_SYSTEM = """\
You are an automation and digital transformation expert. You identify automation opportunities \
in business processes. You classify them by type, maturity, and expected effect. \
Respond ONLY with valid JSON matching the requested schema."""

AUTOMATION_USER = """\
Analyze the following AS-IS process model and identify automation opportunities.

Process: {title}
AS-IS Summary: {summary}
Steps:
{steps_json}

For each automation opportunity, return a JSON array:
[
  {{
    "id": "ap_1",
    "step_id": "step_X",
    "stage": "Name of the process stage",
    "manual_action": "Current manual action being performed",
    "potential": "Description of what can be automated and how",
    "automation_type": "deterministic|intelligent|hybrid",
    "effect": "Expected benefit: time saved, errors reduced, etc.",
    "maturity": "quick_win|short_term|strategic",
    "default_selected": true
  }}
]

Guidelines:
- Look for: repetitive tasks, data entry, rule-based decisions, document processing, \
notifications, approvals, data transfers between systems.
- automation_type: "deterministic" for rule-based/RPA, "intelligent" for AI/ML, "hybrid" for both.
- maturity: "quick_win" (days-weeks), "short_term" (1-3 months), "strategic" (3+ months).
- Set default_selected=true for quick_wins and high-impact items.
- Use the original language of the process for descriptions."""

TOBE_SYSTEM = """\
You are a business process transformation architect. You redesign processes by applying \
selected automation points to create an optimized TO-BE model. \
Respond ONLY with valid JSON matching the requested schema."""

TOBE_USER = """\
Redesign the process based on the AS-IS model and SELECTED automation points.

Process: {title}

AS-IS Summary: {asis_summary}
AS-IS Steps:
{asis_steps_json}

Selected automation points to apply:
{selected_points_json}

Generate a TO-BE process model as JSON:
{{
  "summary": "2-4 sentence summary of the transformed process",
  "steps": [
    {{
      "id": "step_1",
      "name": "Step name",
      "description": "What happens (automated or human)",
      "actor": "Human role OR 'System'/'AI'/'RPA Bot'",
      "systems": ["Tools/platforms involved"],
      "inputs": ["Inputs"],
      "outputs": ["Outputs"],
      "is_decision": false,
      "pain_points": []
    }}
  ],
  "assumptions": ["Assumptions made during redesign"],
  "changes_rationale": ["Why each change was made, linked to automation points"]
}}

Guidelines:
- Remove or simplify steps that are fully automated.
- Replace manual actors with system/AI actors where automation applies.
- Add new automated steps where needed (e.g., auto-validation, notification).
- Keep human steps for oversight, exceptions, and decisions that require judgment.
- Maintain process coherence — the TO-BE must be logically complete.
- Use original language for descriptions."""

TOBE_MERMAID_USER = """\
Create a Mermaid sequence diagram for this TO-BE process.

Process: {title}
Steps (JSON):
{steps_json}

Requirements:
- Use 'sequenceDiagram' type.
- Show human actors AND system/AI actors as participants.
- Visually distinguish automated steps (add note or different participant naming).
- Show the optimized flow clearly.
- Keep labels concise.
- Use the original language from step descriptions."""

HUMAN_ROLE_SYSTEM = """\
You are an organizational design expert specializing in human-machine collaboration. \
You define new human roles in automated processes, focusing on value-added activities. \
Respond ONLY with valid JSON matching the requested schema."""

HUMAN_ROLE_USER = """\
Based on the TO-BE process, define the new human role.

Process: {title}

TO-BE Summary: {tobe_summary}
TO-BE Steps:
{tobe_steps_json}

AS-IS Roles (for context):
{asis_roles_json}

Selected automation points applied:
{selected_points_json}

Return a JSON object:
{{
  "role_name": "New role title",
  "level": "H0|H1|H2|H3",
  "mission": "One-sentence role mission",
  "responsibilities": ["Key responsibility 1", "Key responsibility 2"],
  "boundaries": "What this role does NOT do (handled by automation)",
  "interactions": ["Who/what this role interacts with"],
  "outputs": ["Deliverables and decisions this role produces"],
  "kpis": ["How performance is measured"],
  "tools": ["Tools and systems this role uses"]
}}

Role levels:
- H0 (Operator): Monitors automated processes, handles simple exceptions.
- H1 (Supervisor): Reviews AI outputs, manages escalations, ensures quality.
- H2 (Manager): Makes strategic decisions, manages process performance, drives improvement.
- H3 (Expert): Designs rules, trains AI models, handles complex edge cases, innovates.

Choose the level that best matches the remaining human responsibilities after automation."""
