from __future__ import annotations

import numpy as np

from .._protocol import FilterResult, PatchProposal


def aggregate_proposals(proposals: list[PatchProposal],
                        method: str = "weighted_confidence",
                        area_exponent: float = 0.5,
                        confidence_threshold: float = 0.5) -> FilterResult | None:
    """Aggregate per-patch filter results into a single ROI-level decision."""
    import logging

    _logger = logging.getLogger(__name__)
    valid = [p for p in proposals if p.filter_result is not None]
    if not valid:
        return None

    if method == "max_confidence":
        best = max(valid, key=lambda p: p.filter_result.confidence)
        return best.filter_result

    if method == "weighted_confidence":
        weights = []
        confidences = []
        real_scores = []
        false_scores = []
        for p in valid:
            area = p.proposal_metadata.component_area
            score = p.anomaly_context.anomaly_score
            w = (area ** area_exponent) * score
            weights.append(w)
            confidences.append(p.filter_result.confidence)
            real_scores.append(p.filter_result.real_defect_score)
            false_scores.append(p.filter_result.false_alarm_score)

        w_sum = sum(weights)
        if w_sum == 0:
            return None
        weights_norm = [w / w_sum for w in weights]

        weighted_confidence = sum(w * c for w, c in zip(weights_norm, confidences))
        weighted_real = sum(w * r for w, r in zip(weights_norm, real_scores))
        weighted_false = sum(w * f for w, f in zip(weights_norm, false_scores))

        return FilterResult(
            is_real_defect=weighted_confidence >= confidence_threshold,
            confidence=weighted_confidence,
            real_defect_score=weighted_real,
            false_alarm_score=weighted_false,
            class_id=1 if weighted_confidence >= confidence_threshold else 0,
            diagnostics={
                "num_proposals": len(valid),
                "max_confidence": float(max(confidences)),
                "min_confidence": float(min(confidences)),
                "aggregation_method": method,
            },
        )

    _logger.warning(
        "aggregate_proposals_unknown_method",
        extra={"method": method, "supported": ["max_confidence", "weighted_confidence"]},
    )
    return None
