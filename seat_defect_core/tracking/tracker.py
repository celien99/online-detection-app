from __future__ import annotations

import uuid
from typing import Optional

from .._protocol import PatchProposal

from .config import TrackConfig
from .identity import DefectIdentity, IdentityState
from .kalman_filter import KalmanBoxTracker
from .matcher import CascadeMatcher


class DefectTracker:
    """Per-camera defect identity tracker."""

    def __init__(self, camera_id: str, config: TrackConfig | None = None):
        self.camera_id = camera_id
        self.cfg = config or TrackConfig()
        self._matcher = CascadeMatcher(self.cfg)
        self._identities: dict[str, DefectIdentity] = {}
        self._frame_count: int = 0

    def update(self, proposals: list[PatchProposal]) -> list[PatchProposal]:
        self._frame_count += 1

        # Predict all trackers
        for ident in self._identities.values():
            if ident.tracker is not None:
                ident.tracker.predict()

        # Build proposal dicts for matching (normalize bbox from pixel coords)
        prop_dicts = []
        for p in proposals:
            roi_w, roi_h = p.source_roi.roi_size
            bbox = p.patch_bbox
            w, h = bbox.x2 - bbox.x1, bbox.y2 - bbox.y1
            prop_dicts.append({
                "proposal_id": p.proposal_id,
                "bbox_xywh": (bbox.x1, bbox.y1, w, h),
            })

        active = [i for i in self._identities.values()
                   if i.state not in (IdentityState.DEAD,)]

        matched_pairs, unmatched_props, _ = self._matcher.match(
            prop_dicts, active, self.camera_id)

        # Apply matches
        identity_matches: dict[str, list[int]] = {}
        for p_idx, ident_idx in matched_pairs:
            prop = proposals[p_idx]
            ident = active[ident_idx]
            prop.identity_id = ident.identity_id
            ident.mark_hit()
            if ident.tracker is not None:
                ident.tracker.update(prop_dicts[p_idx]["bbox_xywh"])
            score = prop.anomaly_context.anomaly_score
            if score > ident.best_anomaly_score:
                ident.best_anomaly_score = score
                ident.best_proposal_id = prop.proposal_id
            identity_matches.setdefault(ident.identity_id, []).append(p_idx)

        # N:1 Merge: check if multiple proposals matched same identity
        for iid, p_indices in identity_matches.items():
            if len(p_indices) > 1:
                self._resolve_n_to_one(iid, [proposals[i] for i in p_indices])

        # Create new identities for unmatched proposals
        for p_idx in unmatched_props:
            prop = proposals[p_idx]
            new_id = DefectIdentity(
                identity_id=uuid.uuid4().hex[:12],
                camera_id=self.camera_id,
            )
            bbox = prop_dicts[p_idx]["bbox_xywh"]
            new_id.tracker = KalmanBoxTracker(bbox)
            new_id.best_anomaly_score = prop.anomaly_context.anomaly_score
            new_id.best_proposal_id = prop.proposal_id
            new_id.mark_hit()
            prop.identity_id = new_id.identity_id
            self._identities[new_id.identity_id] = new_id

        # Mark missed identities
        for ident in active:
            ident_id = ident.identity_id
            was_matched = any(active[m[1]].identity_id == ident_id for m in matched_pairs)
            if not was_matched:
                ident.mark_miss()

        # Prune DEAD identities
        for iid, ident in list(self._identities.items()):
            if ident.state == IdentityState.LOST and ident.frames_since_update > self.cfg.max_age:
                ident.state = IdentityState.DEAD

        return proposals

    def get_mature_identities(self) -> list[DefectIdentity]:
        return [i for i in self._identities.values() if i.state == IdentityState.MATURE]

    def merge_identity(self, from_id: str, into_id: str) -> None:
        if from_id in self._identities and into_id in self._identities:
            self._identities[from_id].merged_into = into_id
            self._identities[from_id].state = IdentityState.DEAD

    def _resolve_n_to_one(self, identity_id: str, proposals: list[PatchProposal]):
        proposals.sort(key=lambda p: p.anomaly_context.anomaly_score, reverse=True)
        keep = proposals[0]
        for p in proposals[1:]:
            b1 = keep.patch_bbox
            b2 = p.patch_bbox
            x1 = max(b1.x1, b2.x1); y1 = max(b1.y1, b2.y1)
            x2 = min(b1.x2, b2.x2); y2 = min(b1.y2, b2.y2)
            inter = max(0, x2 - x1) * max(0, y2 - y1)
            area1 = (b1.x2 - b1.x1) * (b1.y2 - b1.y1)
            area2 = (b2.x2 - b2.x1) * (b2.y2 - b2.y1)
            iou_val = inter / (area1 + area2 - inter + 1e-8)
            if iou_val >= 0.5:
                p.identity_id = keep.identity_id
