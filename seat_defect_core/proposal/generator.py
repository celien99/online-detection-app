from __future__ import annotations

from typing import Optional
import uuid

import cv2
import numpy as np

from .._protocol import (
    AnomalyContext,
    BoundingBox,
    EfficientADFeatures,
    ImageRef,
    PatchProposal,
    ProposalMetadata,
    ROIContext,
)

from .config import ProposalConfig
from .budget import BudgetController


class ProposalGenerator:
    """Generate PatchProposals from EfficientAD heatmap + features."""

    def __init__(self, config: ProposalConfig | None = None,
                 budget_ctrl: BudgetController | None = None):
        self.config = config or ProposalConfig()
        self.budget = budget_ctrl or BudgetController(self.config.budget)

    def generate(self, heatmap: np.ndarray, roi_image: np.ndarray,
                 efficientad_features: dict[str, np.ndarray] | None,
                 anomaly_score: float, anomaly_threshold: float,
                 roi_bbox: tuple[int, int, int, int],
                 isolation_key: str,
                 roi_image_key: str = "") -> list[PatchProposal]:
        cfg = self.config

        # Use budget controller for adaptive threshold
        self.budget.start_frame()
        threshold, k_limit, mode = self.budget.regulate(heatmap)

        if mode == "emergency":
            return []  # Emergency exit — skip all proposals

        # 2. Binary threshold + morphological cleanup
        binary = (heatmap > threshold).astype(np.uint8)
        if cfg.open_kernel_size > 0:
            kernel_open = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (cfg.open_kernel_size, cfg.open_kernel_size))
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open)
        if cfg.close_kernel_size > 0:
            kernel_close = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (cfg.close_kernel_size, cfg.close_kernel_size))
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close)

        # 3. Connected components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            binary, connectivity=8)

        self.budget.record_cc_count(num_labels - 1)

        components = []
        for i in range(1, num_labels):
            area = int(stats[i, cv2.CC_STAT_AREA])
            if area < cfg.min_component_area:
                continue
            x = int(stats[i, cv2.CC_STAT_LEFT])
            y = int(stats[i, cv2.CC_STAT_TOP])
            w = int(stats[i, cv2.CC_STAT_WIDTH])
            h = int(stats[i, cv2.CC_STAT_HEIGHT])

            component_mask = (labels == i).astype(np.uint8)
            hull = cv2.convexHull(cv2.findNonZero(component_mask))
            hull_area = cv2.contourArea(hull) if hull is not None else area
            solidity = area / hull_area if hull_area > 0 else 0.0
            if solidity < cfg.min_solidity:
                continue

            patch_score = float(heatmap[component_mask > 0].mean()) if area > 0 else 0.0
            components.append((area, solidity, patch_score, x, y, w, h))

        if not components:
            return []

        # Sort by area * score descending
        components.sort(key=lambda c: c[0] * c[2], reverse=True)
        # Apply budget limit alongside max_proposals
        effective_max = min(cfg.max_proposals, k_limit if k_limit > 0 else cfg.max_proposals)
        components = components[:effective_max]

        roi_h, roi_w = roi_image.shape[:2]
        roi_context = ROIContext(
            roi_bbox=BoundingBox(*roi_bbox),
            roi_image_ref=ImageRef(
                key=roi_image_key or f"roi/{uuid.uuid4().hex[:8]}.jpg",
                width=roi_w, height=roi_h),
            roi_size=(roi_w, roi_h),
        )

        proposals: list[PatchProposal] = []
        for rank, (area, solidity, pscore, x, y, w, h) in enumerate(components):
            pad_w = int(w * cfg.context_padding_ratio)
            pad_h = int(h * cfg.context_padding_ratio)
            x1 = max(0, x - pad_w)
            y1 = max(0, y - pad_h)
            x2 = min(roi_w, x + w + pad_w)
            y2 = min(roi_h, y + h + pad_h)

            if (x2 - x1) < cfg.min_crop_size or (y2 - y1) < cfg.min_crop_size:
                continue

            pid = uuid.uuid4().hex[:12]
            patch_bbox = BoundingBox(float(x1), float(y1), float(x2), float(y2))

            feat_prefix = f"features/{isolation_key.replace('|', '/')}/{pid}"
            ead_feats = EfficientADFeatures(
                teacher_ref=f"{feat_prefix}/teacher.npy" if efficientad_features else "",
                student_ref=f"{feat_prefix}/student.npy" if efficientad_features else "",
                difference_ref=f"{feat_prefix}/difference.npy" if efficientad_features else "",
            )

            anomaly_ctx = AnomalyContext(
                anomaly_score=pscore,
                anomaly_threshold=anomaly_threshold,
                heatmap_ref=ImageRef(key=f"{feat_prefix}/heatmap.png"),
                feature_ref=feat_prefix,
            )

            proposals.append(PatchProposal(
                proposal_id=pid,
                isolation_key=isolation_key,
                source_roi=roi_context,
                patch_image=ImageRef(key=f"{feat_prefix}/patch.png",
                                     width=x2 - x1, height=y2 - y1),
                patch_bbox=patch_bbox,
                anomaly_context=anomaly_ctx,
                efficientad_features=ead_feats,
                proposal_metadata=ProposalMetadata(
                    component_area=area,
                    component_solidity=solidity,
                    rank=rank + 1,
                    total_proposals=len(components),
                    generation_params={
                        "threshold": threshold,
                        "threshold_mode": cfg.heatmap_threshold_mode,
                    },
                ),
            ))

        return proposals

    def extract_patch_crops(self, roi_image: np.ndarray,
                            proposals: list[PatchProposal]) -> list[np.ndarray]:
        """Extract image crops for each proposal from the ROI image."""
        crops = []
        for p in proposals:
            b = p.patch_bbox
            crop = roi_image[int(b.y1):int(b.y2), int(b.x1):int(b.x2)]
            crops.append(crop)
        return crops

    def extract_patch_features(self, efficientad_features: dict[str, np.ndarray],
                               proposals: list[PatchProposal],
                               roi_size: tuple[int, int]) -> list[dict[str, np.ndarray]]:
        """Extract EfficientAD features for each proposal's spatial region."""
        roi_h, roi_w = roi_size
        patch_features = []
        for p in proposals:
            b = p.patch_bbox
            pf: dict[str, np.ndarray] = {}
            for key, feat_map in efficientad_features.items():
                if feat_map.ndim < 2:
                    continue
                fh, fw = feat_map.shape[0], feat_map.shape[1]
                fx1 = max(0, int(b.x1 * fw / roi_w))
                fy1 = max(0, int(b.y1 * fh / roi_h))
                fx2 = min(fw, int(b.x2 * fw / roi_w))
                fy2 = min(fh, int(b.y2 * fh / roi_h))
                if fx2 <= fx1 or fy2 <= fy1:
                    continue
                pf[key] = feat_map[fy1:fy2, fx1:fx2]
            patch_features.append(pf)
        return patch_features
