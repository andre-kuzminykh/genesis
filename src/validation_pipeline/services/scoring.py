"""Scoring engine — scores ideas against validation dimensions."""

import uuid
from collections import defaultdict

from validation_pipeline.config import settings
from validation_pipeline.models.entities import (
    ConfidenceLevel,
    DimensionScore,
    EvidenceItem,
    Recommendation,
    ScoreCard,
    ValidationRun,
)

CONFIDENCE_WEIGHTS = {
    ConfidenceLevel.high: 1.0,
    ConfidenceLevel.medium: 0.6,
    ConfidenceLevel.low: 0.3,
}

DIMENSION_WEIGHTS = {
    "problem_clarity": 0.25,
    "target_user_definition": 0.20,
    "market_opportunity": 0.15,
    "solution_feasibility": 0.20,
    "competitive_landscape": 0.10,
    "assumptions_risk": 0.10,
}


class ScoringEngine:
    def score(
        self, run: ValidationRun, evidence_items: list[EvidenceItem]
    ) -> ScoreCard:
        evidence_by_dim: dict[str, list[EvidenceItem]] = defaultdict(list)
        for item in evidence_items:
            evidence_by_dim[item.dimension].append(item)

        dimension_scores: list[DimensionScore] = []
        for dimension, weight in DIMENSION_WEIGHTS.items():
            items = evidence_by_dim.get(dimension, [])
            ds = self._score_dimension(dimension, items)
            dimension_scores.append(ds)

        overall = self._compute_overall(dimension_scores)
        overall_confidence = self._overall_confidence(dimension_scores)
        recommendation = self._decide_recommendation(overall, overall_confidence)

        follow_ups = self._generate_follow_ups(dimension_scores)
        next_steps = self._generate_next_steps(recommendation, dimension_scores)

        card = ScoreCard(
            run_id=run.id,
            overall_score=overall,
            overall_confidence=overall_confidence,
            recommendation=recommendation,
            recommendation_rationale=self._rationale(
                recommendation, overall, overall_confidence, dimension_scores
            ),
            next_steps=next_steps,
            follow_up_questions=follow_ups,
        )
        card.dimension_scores = dimension_scores
        return card

    def _score_dimension(
        self, dimension: str, items: list[EvidenceItem]
    ) -> DimensionScore:
        if not items:
            return DimensionScore(
                dimension=dimension,
                score=0.0,
                confidence=ConfidenceLevel.low,
                rationale="No evidence available for this dimension.",
                missing_evidence=f"No data collected for {dimension}.",
            )

        best_confidence = max(items, key=lambda i: CONFIDENCE_WEIGHTS[i.confidence])
        conf = best_confidence.confidence
        score = CONFIDENCE_WEIGHTS[conf]

        missing = None
        if conf == ConfidenceLevel.low:
            missing = f"Insufficient evidence for {dimension}. Consider providing more detail."

        return DimensionScore(
            dimension=dimension,
            score=round(score, 2),
            confidence=conf,
            rationale=f"Based on {len(items)} evidence item(s). Best confidence: {conf.value}.",
            missing_evidence=missing,
        )

    def _compute_overall(self, scores: list[DimensionScore]) -> float:
        total_weight = 0.0
        weighted_sum = 0.0
        for ds in scores:
            w = DIMENSION_WEIGHTS.get(ds.dimension, 0.1)
            weighted_sum += ds.score * w
            total_weight += w
        return round(weighted_sum / total_weight if total_weight > 0 else 0.0, 2)

    def _overall_confidence(self, scores: list[DimensionScore]) -> ConfidenceLevel:
        low_count = sum(1 for ds in scores if ds.confidence == ConfidenceLevel.low)
        if low_count >= len(scores) / 2:
            return ConfidenceLevel.low
        high_count = sum(1 for ds in scores if ds.confidence == ConfidenceLevel.high)
        if high_count >= len(scores) / 2:
            return ConfidenceLevel.high
        return ConfidenceLevel.medium

    def _decide_recommendation(
        self, score: float, confidence: ConfidenceLevel
    ) -> Recommendation:
        if confidence == ConfidenceLevel.low:
            return Recommendation.iterate
        if score >= settings.proceed_threshold:
            return Recommendation.proceed
        if score >= settings.iterate_threshold:
            return Recommendation.iterate
        return Recommendation.reject

    def _rationale(
        self,
        rec: Recommendation,
        score: float,
        conf: ConfidenceLevel,
        scores: list[DimensionScore],
    ) -> str:
        weak = [ds.dimension for ds in scores if ds.confidence == ConfidenceLevel.low]
        strong = [ds.dimension for ds in scores if ds.confidence == ConfidenceLevel.high]
        parts = [
            f"Overall score: {score:.2f} with {conf.value} confidence.",
            f"Recommendation: {rec.value}.",
        ]
        if strong:
            parts.append(f"Strong dimensions: {', '.join(strong)}.")
        if weak:
            parts.append(f"Weak dimensions needing attention: {', '.join(weak)}.")
        return " ".join(parts)

    def _generate_follow_ups(self, scores: list[DimensionScore]) -> str | None:
        questions = []
        for ds in scores:
            if ds.confidence == ConfidenceLevel.low:
                questions.append(f"- {ds.dimension}: {ds.missing_evidence or 'Provide more data.'}")
        return "\n".join(questions) if questions else None

    def _generate_next_steps(
        self, rec: Recommendation, scores: list[DimensionScore]
    ) -> str:
        steps = []
        if rec == Recommendation.proceed:
            steps.append("- Move to discovery phase.")
            steps.append("- Define MVP scope based on validated assumptions.")
        elif rec == Recommendation.iterate:
            weak = [ds.dimension for ds in scores if ds.confidence == ConfidenceLevel.low]
            steps.append("- Address low-confidence areas before proceeding.")
            for dim in weak:
                steps.append(f"  - Strengthen evidence for: {dim}")
            steps.append("- Rerun validation after updates.")
        else:
            steps.append("- Consider pivoting or discarding this idea.")
            steps.append("- Review weak dimensions for potential salvageable elements.")
        return "\n".join(steps)
