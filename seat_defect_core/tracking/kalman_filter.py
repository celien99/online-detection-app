from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment


class KalmanBoxTracker:
    """6-DOF Kalman filter: (x, y, w, h, vx, vy)."""

    def __init__(self, bbox: tuple[float, float, float, float]):
        x, y, w, h = bbox
        self.kf = self._init_kalman()
        self.kf.state_est[:4, 0] = np.array([x, y, w, h], dtype=np.float32)
        self.time_since_update = 0
        self.hits = 0
        self.hit_streak = 0
        self.age = 0

    def _init_kalman(self):
        import cv2
        kf = cv2.KalmanFilter(6, 4)
        kf.transitionMatrix = np.eye(6, dtype=np.float32)
        kf.transitionMatrix[0, 4] = 1.0
        kf.transitionMatrix[1, 5] = 1.0
        kf.measurementMatrix = np.eye(4, 6, dtype=np.float32)
        kf.processNoiseCov *= 0.01
        kf.measurementNoiseCov *= 0.1
        return kf

    def predict(self) -> tuple[float, float, float, float]:
        pred = self.kf.predict()
        x, y, w, h = pred[0, 0], pred[1, 0], pred[2, 0], pred[3, 0]
        self.age += 1
        self.time_since_update += 1
        return (x, y, w, h)

    def update(self, bbox: tuple[float, float, float, float]):
        x, y, w, h = bbox
        self.kf.correct(np.array([[x], [y], [w], [h]], dtype=np.float32))
        self.time_since_update = 0
        self.hits += 1
        self.hit_streak += 1

    def mahalanobis(self, bbox: tuple[float, float, float, float]) -> float:
        pred = self.kf.state_pre[:4, 0]
        meas = np.array(bbox, dtype=np.float32)
        innov = meas - pred
        S = self.kf.measurementMatrix @ self.kf.errorCovPre @ self.kf.measurementMatrix.T + self.kf.measurementNoiseCov
        try:
            return float(np.sqrt(innov.T @ np.linalg.inv(S) @ innov))
        except np.linalg.LinAlgError:
            return float("inf")


def iou(bbox1: tuple, bbox2: tuple) -> float:
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[0] + bbox1[2], bbox2[0] + bbox2[2])
    y2 = min(bbox1[1] + bbox1[3], bbox2[1] + bbox2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = bbox1[2] * bbox1[3]
    area2 = bbox2[2] * bbox2[3]
    return inter / (area1 + area2 - inter + 1e-8)


def hungarian_matching(cost_matrix: np.ndarray) -> list[tuple[int, int]]:
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    return list(zip(row_ind.tolist(), col_ind.tolist()))
