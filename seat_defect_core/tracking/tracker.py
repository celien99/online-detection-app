from __future__ import annotations

import uuid
from typing import Optional

from .._protocol import CanonicalPatchProposal

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

    def update(self, proposals: list[CanonicalPatchProposal]) -> list[CanonicalPatchProposal]:
        self._frame_count += 1

        # Predict all trackers
        for ident in self._identities.values():
            if ident.tracker is not None:
                ident.tracker.predict()

        # Build proposal dicts for matching
        prop_dicts = []
        for p in proposals:
            bbox_norm = p.patch_bbox_norm
            w, h = p.roi_size_px
            prop_dicts.append({
                "proposal_id": p.proposal_id,
                "bbox_xywh": (bbox_norm[0] * w, bbox_norm[1] * h,
                              (bbox_norm[2] - bbox_norm[0]) * w,
                              (bbox_norm[3] - bbox_norm[1]) * h),
                "unified_embedding": p.unified_embedding,
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
            if prop.anomaly_score > ident.best_anomaly_score:
                ident.best_anomaly_score = prop.anomaly_score
                ident.best_proposal_id = prop.proposal_id
                ident.best_patch_bbox_norm = prop.patch_bbox_norm
            if prop.unified_embedding:
                ident.unified_embedding = prop.unified_embedding
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
            new_id.best_anomaly_score = prop.anomaly_score
            new_id.best_proposal_id = prop.proposal_id
            new_id.best_patch_bbox_norm = prop.patch_bbox_norm
            if prop.unified_embedding:
                new_id.unified_embedding = prop.unified_embedding
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

    def _resolve_n_to_one(self, identity_id: str, proposals: list[CanonicalPatchProposal]):
        proposals.sort(key=lambda p: p.anomaly_score, reverse=True)
        keep = proposals[0]
        for p in proposals[1:]:
            b1 = keep.patch_bbox_norm
            b2 = p.patch_bbox_norm
            x1 = max(b1[0], b2[0]); y1 = max(b1[1], b2[1])
            x2 = min(b1[2], b2[2]); y2 = min(b1[3], b2[3])
            inter = max(0, x2 - x1) * max(0, y2 - y1)
            area1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
            area2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
            iou_val = inter / (area1 + area2 - inter + 1e-8)
            if iou_val >= 0.5:
                p.identity_id = keep.identity_id
