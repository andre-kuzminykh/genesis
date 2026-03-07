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
