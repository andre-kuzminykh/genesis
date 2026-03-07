"""API endpoint tests."""

import pytest
from httpx import AsyncClient


VALID_IDEA = {
    "idea": {
        "title": "AI-powered code review assistant",
        "target_user": "Software engineering teams at mid-size companies who struggle with review bottlenecks",
        "problem_statement": (
            "Code reviews are a major bottleneck in the software development lifecycle. "
            "Teams spend hours reviewing code manually, leading to delayed releases and inconsistent quality."
        ),
        "proposed_solution": (
            "Build an AI-powered code review tool that automatically analyzes pull requests, "
            "identifies potential issues, suggests improvements, and learns from team patterns."
        ),
        "assumptions": "Teams are willing to adopt AI tools; existing CI/CD pipelines can integrate.",
        "market_context": "Growing market for developer tools. GitHub Copilot proves AI adoption in dev workflows.",
    }
}


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_validation_run(client: AsyncClient):
    resp = await client.post("/validation-runs", json=VALID_IDEA)
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["state"] == "created"
    assert data["iteration_number"] == 1


@pytest.mark.asyncio
async def test_create_run_missing_fields(client: AsyncClient):
    resp = await client.post(
        "/validation-runs",
        json={"idea": {"title": "X"}},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_run_empty_title(client: AsyncClient):
    idea = VALID_IDEA.copy()
    idea["idea"] = {**idea["idea"], "title": "ab"}
    resp = await client.post("/validation-runs", json=idea)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_run_status(client: AsyncClient):
    create_resp = await client.post("/validation-runs", json=VALID_IDEA)
    run_id = create_resp.json()["id"]

    resp = await client.get(f"/validation-runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == run_id


@pytest.mark.asyncio
async def test_get_run_not_found(client: AsyncClient):
    resp = await client.get("/validation-runs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_report_after_pipeline(client: AsyncClient):
    """Pipeline runs in background and completes before report fetch."""
    create_resp = await client.post("/validation-runs", json=VALID_IDEA)
    run_id = create_resp.json()["id"]

    resp = await client.get(f"/validation-runs/{run_id}/report")
    assert resp.status_code == 200
    report = resp.json()
    assert report["score_card"] is not None
    assert report["score_card"]["recommendation"] in ("proceed", "iterate", "reject")
    assert len(report["evidence"]) > 0


@pytest.mark.asyncio
async def test_get_report_not_found(client: AsyncClient):
    resp = await client.get("/validation-runs/00000000-0000-0000-0000-000000000000/report")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_events(client: AsyncClient):
    create_resp = await client.post("/validation-runs", json=VALID_IDEA)
    run_id = create_resp.json()["id"]

    resp = await client.get(f"/validation-runs/{run_id}/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    assert events[0]["to_state"] == "created"
