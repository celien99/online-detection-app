from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .kalman_filter import KalmanBoxTracker


class IdentityState(Enum):
    BIRTH = "birth"
    ACTIVE = "active"
    TENTATIVE = "tentative"
    MATURE = "mature"
    LOST = "lost"
    DEAD = "dead"


@dataclass
class DefectIdentity:
    identity_id: str
    camera_id: str
    state: IdentityState = IdentityState.BIRTH
    tracker: Optional[KalmanBoxTracker] = None
    best_anomaly_score: float = 0.0
    best_frame_id: str = ""
    best_proposal_id: str = ""
    best_patch_bbox_norm: tuple[float, float, float, float] = (0, 0, 0, 0)
    unified_embedding: Optional[list[float]] = None
    merged_into: Optional[str] = None
    frames_since_update: int = 0
    total_hits: int = 0
    hit_streak: int = 0

    def mark_hit(self):
        self.total_hits += 1
        self.hit_streak += 1
        self.frames_since_update = 0
        if self.hit_streak >= 5:
            self.state = IdentityState.MATURE
        elif self.hit_streak >= 2:
            self.state = IdentityState.TENTATIVE
        elif self.state == IdentityState.BIRTH:
            self.state = IdentityState.ACTIVE

    def mark_miss(self):
        self.frames_since_update += 1
        self.hit_streak = 0
        if self.frames_since_update > 0:
            self.state = IdentityState.LOST
