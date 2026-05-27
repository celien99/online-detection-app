from __future__ import annotations

import numpy as np

from .config import TrackConfig
from .identity import DefectIdentity
from .kalman_filter import hungarian_matching, iou


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = np.sqrt(sum(x * x for x in a))
    norm_b = np.sqrt(sum(x * x for x in b))
    return float(dot / (norm_a * norm_b + 1e-8))


class CascadeMatcher:
    """Three-stage cascade matching with conflict resolution."""

    def __init__(self, config: TrackConfig):
        self.cfg = config

    def match(self, proposals: list[dict], active_identities: list[DefectIdentity],
              camera_id: str) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        n_props = len(proposals)
        n_idents = len(active_identities)
        if n_props == 0:
            return ([], [], list(range(n_idents)))

        matched: list[tuple[int, int]] = []
        unmatched_props = set(range(n_props))

        # Stage 1: IoU + Kalman (same-camera only)
        unmatched_props = self._match_stage(matched, unmatched_props, proposals,
                                             active_identities, camera_id, stage=1)
        # Stage 2: Feature cosine similarity
        if unmatched_props:
            unmatched_props = self._match_stage(matched, unmatched_props, proposals,
                                                 active_identities, camera_id, stage=2)

        unmatched_idents = list(set(range(n_idents)) - {j for _, j in matched})
        return (matched, list(unmatched_props), unmatched_idents)

    def _match_stage(self, matched: list, unmatched_props: set, proposals: list[dict],
                     identities: list[DefectIdentity], camera_id: str,
                     stage: int) -> set:
        if not unmatched_props:
            return unmatched_props

        cost_matrix = np.full((len(unmatched_props), len(identities)), np.inf)
        prop_indices = sorted(unmatched_props)

        for pi, p_idx in enumerate(prop_indices):
            p = proposals[p_idx]
            for ii, ident in enumerate(identities):
                if stage == 1:
                    if ident.camera_id != camera_id or ident.tracker is None:
                        continue
                    pred_bbox = ident.tracker.predict()
                    iou_val = iou(p["bbox_xywh"], pred_bbox)
                    mahal = ident.tracker.mahalanobis(p["bbox_xywh"])
                    if iou_val >= self.cfg.iou_threshold and mahal <= self.cfg.mahalanobis_threshold:
                        cost_matrix[pi, ii] = 1.0 - iou_val
                elif stage == 2:
                    if p.get("unified_embedding") is None or ident.unified_embedding is None:
                        continue
                    cos_sim = cosine_similarity(p["unified_embedding"], ident.unified_embedding)
                    if cos_sim >= self.cfg.feature_cosine_threshold:
                        cost_matrix[pi, ii] = 1.0 - cos_sim

        valid = cost_matrix < np.inf
        if valid.any():
            assignments = hungarian_matching(cost_matrix)
            for pi, ii in assignments:
                if cost_matrix[pi, ii] < np.inf:
                    # Best Match Wins: check margin
                    row = cost_matrix[pi, :]
                    sorted_costs = sorted(row[row < np.inf])
                    if len(sorted_costs) >= 2:
                        margin = sorted_costs[1] - sorted_costs[0]
                        if margin < self.cfg.feature_match_margin:
                            continue  # ambiguous → create new identity
                    matched.append((prop_indices[pi], ii))
                    unmatched_props.discard(prop_indices[pi])

        return unmatched_props
