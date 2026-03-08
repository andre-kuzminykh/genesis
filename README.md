# Idea Validation Pipeline

AI-assisted pipeline that validates product/business ideas against predefined criteria, collects evidence, scores viability, and produces structured reports with recommendations.

## Architecture

- **validation-api** — FastAPI service: idea submission, run management, report retrieval
- **validation-orchestrator** — Pipeline state machine: input validation → enrichment → scoring → report generation
- **scoring-engine** — Scores ideas across 6 dimensions with confidence labeling
- **report-generator** — Assembles structured validation reports
- **Streamlit UI** — Web interface for submission, status tracking, reports, and reruns

## Quick Start

```bash
# Run with Docker Compose
docker compose up --build

# API: http://localhost:8000
# UI:  http://localhost:8501
# Docs: http://localhost:8000/docs
```

## Local Development

```bash
pip install -e ".[dev]"

# Run API
uvicorn validation_pipeline.app:app --reload

# Run UI
streamlit run streamlit_app.py

# Run tests
pytest
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/validation-runs` | Submit idea for validation |
| GET | `/validation-runs/{id}` | Get run status |
| GET | `/validation-runs/{id}/report` | Get validation report |
| GET | `/validation-runs/{id}/events` | Get state transition log |
| POST | `/validation-runs/{id}/rerun` | Create new iteration |
| GET | `/validation-runs/{id}/history` | Get iteration history |

## Validation Dimensions

- Problem Clarity
- Target User Definition
- Market Opportunity
- Solution Feasibility
- Competitive Landscape
- Assumptions Risk

## Pipeline States

`created` → `validating_input` → `enriching` → `scoring` → `report_ready` / `report_ready_low_confidence` / `failed`

---

## Process Automation Designer — PRD

### Overview

Streamlit-based tool for analyzing business processes, identifying automation opportunities, and designing optimized (TO-BE) processes with new human roles.

### Functional Requirements

#### 1. Process Creation and List
- User enters a process name.
- After creation the new process appears in the left sidebar menu.
- All created processes accumulate in the list.
- User can select any process from the sidebar and view:
  - its final rendered view;
  - its final HTML report.

#### 2. Process Input Data
For a selected process the user can:
- Enter a text description;
- Upload or paste audio;
- Record additional audio directly in the interface.

After all data is entered the system processes it and opens the next page.

#### 3. AS-IS Screen
After input the AS-IS page shows:
- HTML representation of the process;
- Mermaid diagram of the AS-IS state.

**Visual requirement:** background must be white or Mermaid diagram must be styled so it does not blend with a dark background. The diagram must always be clearly readable.

#### 4. Automation Point Selection
On the AS-IS screen the user sees automation points and can select them.

Each automation point displays:
- Operation name;
- Explanation of what happens at that step;
- Human role in the operation;
- Description of:
  - what the system does;
  - what the human does;
  - how the interaction works.

#### 5. TO-BE Screen
After selecting automation points the system generates the TO-BE screen showing:
- New Mermaid diagram (TO-BE);
- Updated process description;
- New human role in operations.

#### 6. Human Role Assignment
For each operation in TO-BE the user can assign a new human role in one of 4 modes:
- **H0** — Operator
- **H1** — Supervisor
- **H2** — Manager
- **H3** — Expert

#### 7. Final Result
When the user clicks "Done" a final HTML page is assembled.

At the top of the page there are only two toggles:
- **Switch AS-IS**
- **Switch TO-BE**

**AS-IS mode** shows:
- Full process;
- Complete process description;
- Mermaid diagram AS-IS;
- Highlighted automation points.

**TO-BE mode** shows:
- Mermaid diagram TO-BE;
- Complete description of the updated process;
- New human role at the bottom.

#### 8. Sidebar Structure
- List of all created processes;
- Processes accumulate;
- Any previously created process can be opened.

### User Flow
1. Enter process name.
2. Enter text.
3. Add audio.
4. Optionally record additional audio.
5. Navigate to AS-IS screen.
6. View HTML and Mermaid diagram.
7. Select automation points.
8. Navigate to TO-BE screen.
9. Assign new human role: H0 / H1 / H2 / H3.
10. Click "Done".
11. Receive final HTML page with AS-IS / TO-BE toggle.
