from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrackConfig:
    max_age: int = 30
    min_hits: int = 2
    mature_hits: int = 5
    iou_threshold: float = 0.3
    mahalanobis_threshold: float = 9.5
    feature_cosine_threshold: float = 0.85
    feature_match_margin: float = 0.15
    nms_iou_threshold: float = 0.5
    cross_camera_cosine_threshold: float = 0.9
    epipolar_distance_threshold: float = 50.0
