"""Unit tests for the scoring engine."""

import uuid
from types import SimpleNamespace

from validation_pipeline.models.entities import (
    ConfidenceLevel,
    Recommendation,
)
from validation_pipeline.services.scoring import ScoringEngine


def _make_run():
    return SimpleNamespace(id=uuid.uuid4())


def _make_evidence(dimension: str, confidence: ConfidenceLevel):
    return SimpleNamespace(
        dimension=dimension,
        source="test",
        content="Test evidence content",
        confidence=confidence,
    )


def test_score_all_high_confidence():
    engine = ScoringEngine()
    run = _make_run()
    evidence = [
        _make_evidence("problem_clarity", ConfidenceLevel.high),
        _make_evidence("target_user_definition", ConfidenceLevel.high),
        _make_evidence("market_opportunity", ConfidenceLevel.high),
        _make_evidence("solution_feasibility", ConfidenceLevel.high),
        _make_evidence("competitive_landscape", ConfidenceLevel.high),
        _make_evidence("assumptions_risk", ConfidenceLevel.high),
    ]
    card = engine.score(run, evidence)
    assert card.overall_score == 1.0
    assert card.overall_confidence == ConfidenceLevel.high
    assert card.recommendation == Recommendation.proceed


def test_score_all_low_confidence():
    engine = ScoringEngine()
    run = _make_run()
    evidence = [
        _make_evidence("problem_clarity", ConfidenceLevel.low),
        _make_evidence("target_user_definition", ConfidenceLevel.low),
        _make_evidence("market_opportunity", ConfidenceLevel.low),
        _make_evidence("solution_feasibility", ConfidenceLevel.low),
        _make_evidence("competitive_landscape", ConfidenceLevel.low),
        _make_evidence("assumptions_risk", ConfidenceLevel.low),
    ]
    card = engine.score(run, evidence)
    assert card.overall_confidence == ConfidenceLevel.low
    assert card.recommendation == Recommendation.iterate
    assert card.follow_up_questions is not None


def test_score_mixed_confidence():
    engine = ScoringEngine()
    run = _make_run()
    evidence = [
        _make_evidence("problem_clarity", ConfidenceLevel.high),
        _make_evidence("target_user_definition", ConfidenceLevel.high),
        _make_evidence("market_opportunity", ConfidenceLevel.low),
        _make_evidence("solution_feasibility", ConfidenceLevel.medium),
        _make_evidence("competitive_landscape", ConfidenceLevel.low),
        _make_evidence("assumptions_risk", ConfidenceLevel.medium),
    ]
    card = engine.score(run, evidence)
    assert card.overall_confidence == ConfidenceLevel.medium
    assert len(card.dimension_scores) == 6


def test_score_no_evidence():
    engine = ScoringEngine()
    run = _make_run()
    card = engine.score(run, [])
    assert card.overall_score == 0.0
    assert card.recommendation == Recommendation.iterate


def test_follow_up_questions_for_low_confidence():
    engine = ScoringEngine()
    run = _make_run()
    evidence = [
        _make_evidence("problem_clarity", ConfidenceLevel.high),
        _make_evidence("market_opportunity", ConfidenceLevel.low),
    ]
    card = engine.score(run, evidence)
    assert card.follow_up_questions is not None
    assert "market_opportunity" in card.follow_up_questions
