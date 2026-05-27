"""EMA-based feature center tracking for defect types."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class DefectCenter:
    """单个 defect_type 的 EMA 特征中心。"""

    defect_type: str
    center: np.ndarray  # (dim,) EMA 中心
    sample_count: int
    variance: np.ndarray  # (dim,) 类内方差 EMA
    last_updated: str = ""  # ISO timestamp

    def to_dict(self) -> dict:
        return {
            "defect_type": self.defect_type,
            "center": self.center.tolist(),
            "sample_count": self.sample_count,
            "variance": self.variance.tolist(),
            "last_updated": self.last_updated,
        }


class EMAFeatureCenter:
    """维护所有已知 defect_type 的特征中心 EMA。

    Key: defect_type（跨机位，calibration 之后特征已统一）
    更新：center = alpha * center + (1-alpha) * new_embedding
    方差：variance = alpha * variance + (1-alpha) * (new - center)^2

    用途：
    - Filter Classifier 训练的辅助特征（center_distance）
    - KNN 检索（找与当前 proposal 最相似的已知缺陷）
    - 新缺陷发现（距离所有已知中心都远的 proposal -> is_novel）
    """

    def __init__(self, alpha: float = 0.99, dim: int = 384):
        self.alpha = alpha
        self._dim = dim
        self._centers: dict[str, DefectCenter] = {}

    def update(self, defect_type: str, embedding: np.ndarray) -> DefectCenter:
        """用新 embedding 更新 defect_type 的 EMA 中心。
        如果 defect_type 不存在则创建。
        """
        existing = self._centers.get(defect_type)
        if existing is None:
            center = DefectCenter(
                defect_type=defect_type,
                center=embedding.astype(np.float32).copy(),
                sample_count=1,
                variance=np.zeros(self._dim, dtype=np.float32),
                last_updated=datetime.now(timezone.utc).isoformat(),
            )
            self._centers[defect_type] = center
            return center

        emb = np.asarray(embedding, dtype=np.float32)
        old_center = existing.center
        diff = emb - old_center
        existing.center = (
            self.alpha * old_center + (1.0 - self.alpha) * emb
        )
        existing.variance = (
            self.alpha * existing.variance
            + (1.0 - self.alpha) * (diff * diff)
        )
        existing.sample_count += 1
        existing.last_updated = datetime.now(timezone.utc).isoformat()
        return existing

    def query_nearest(
        self, embedding: np.ndarray, top_k: int = 5
    ) -> list[tuple[str, float]]:
        """返回距离最近的 top_k 个 defect_type 及余弦距离。

        要求调用方保证 embedding 是 L2 归一化向量（||x||_2 ≈ 1.0）。
        """
        if not self._centers:
            return []
        emb = embedding.astype(np.float32)
        distances: list[tuple[str, float]] = []
        for dtype, center in self._centers.items():
            dot = np.dot(emb, center.center)
            dist = 1.0 - dot  # 两个 L2 归一化向量的余弦距离
            distances.append((dtype, float(dist)))
        distances.sort(key=lambda x: x[1])
        return distances[:top_k]

    def mahalanobis_distance(
        self, defect_type: str, embedding: np.ndarray
    ) -> Optional[float]:
        """计算到指定 defect_type 中心的马氏距离。"""
        center = self._centers.get(defect_type)
        if center is None or center.sample_count < 2:
            return None
        diff = embedding.astype(np.float32) - center.center
        var = center.variance + 1e-8
        return float(np.sqrt(np.sum(diff * diff / var)))

    def is_novel(self, embedding: np.ndarray, threshold: float) -> bool:
        """判断 embedding 是否代表新类型缺陷。
        距离所有已知中心都超过 threshold 则视为 novel。
        """
        nearest = self.query_nearest(embedding, top_k=1)
        if not nearest:
            return True
        return nearest[0][1] > threshold

    def get_center(self, defect_type: str) -> Optional[DefectCenter]:
        return self._centers.get(defect_type)

    def list_types(self) -> list[str]:
        return sorted(self._centers.keys())

    def center_count(self) -> int:
        return len(self._centers)

    def save(self, path: str) -> None:
        """保存所有中心到 JSON 文件。"""
        data = {
            "alpha": self.alpha,
            "dim": self._dim,
            "centers": [c.to_dict() for c in self._centers.values()],
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, path: str) -> "EMAFeatureCenter":
        """从 JSON 文件加载所有中心。"""
        data = json.loads(Path(path).read_text("utf-8"))
        instance = cls(alpha=data["alpha"], dim=data["dim"])
        for cdata in data["centers"]:
            center = DefectCenter(
                defect_type=cdata["defect_type"],
                center=np.array(cdata["center"], dtype=np.float32),
                sample_count=cdata["sample_count"],
                variance=np.array(cdata["variance"], dtype=np.float32),
                last_updated=cdata.get("last_updated", ""),
            )
            instance._centers[center.defect_type] = center
        return instance
