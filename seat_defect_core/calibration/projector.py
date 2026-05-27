"""Project EfficientAD multi-scale features to 384-dim unified embedding space."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

_logger = logging.getLogger(__name__)


@dataclass
class ProjectionParams:
    """Precomputed projection parameters."""
    weights: np.ndarray       # (concat_dim, output_dim)
    bias: np.ndarray          # (output_dim,)
    pool_sizes: dict[str, tuple[int, int]]  # per-key adaptive pool target (H, W)
    input_keys: list[str]     # ordered keys for concatenation


class EmbeddingProjector:
    """EfficientAD 多尺度特征图 → 384-dim L2 归一化 UnifiedEmbedding。

    流程：
    1. 各尺度 feature map → adaptive average pool → 固定尺寸向量
    2. 按 input_keys 顺序 concat
    3. y = concat_vec @ weights + bias
    4. y / ||y||_2 → 输出 384-dim L2 归一化向量

    投影矩阵离线训练（PCA 初始化 + linear probe finetune）后存为 .npz。
    """

    def __init__(self):
        self._params: Optional[ProjectionParams] = None

    def project(self, features: dict[str, np.ndarray]) -> np.ndarray:
        """将特征字典投影到 384-dim L2 归一化向量。

        Returns:
            (384,) float32 numpy array, L2 norm ≈ 1.0
        """
        if self._params is None:
            raise RuntimeError("Projector not fitted or loaded")

        pooled_vecs = []
        for key in self._params.input_keys:
            feat = features.get(key)
            if feat is None:
                raise KeyError(f"Missing feature key '{key}' for projection")
            pooled = self._adaptive_pool(feat, self._params.pool_sizes[key])
            pooled_vecs.append(pooled)

        concat = np.concatenate(pooled_vecs)
        y = np.asarray(concat, dtype=np.float32) @ self._params.weights + self._params.bias
        norm = np.linalg.norm(y)
        if norm > 1e-8:
            y = y / norm
        else:
            _logger.warning(
                "projection_near_zero_norm",
                extra={"norm": float(norm)},
            )
        return y.astype(np.float32)

    @staticmethod
    def _adaptive_pool(feature_map: np.ndarray, target_size: tuple[int, int]) -> np.ndarray:
        """Spatial adaptive average pool for a single feature map.

        Args:
            feature_map: (H, W, C) array
            target_size: (out_h, out_w) — typically (1,1) for global pooling

        Returns:
            (channels * out_h * out_w,) flattened vector
        """
        h, w, c = feature_map.shape
        out_h, out_w = target_size

        result = np.zeros((out_h, out_w, c), dtype=np.float32)
        for i in range(out_h):
            for j in range(out_w):
                y1 = int(i * h / out_h)
                y2 = int((i + 1) * h / out_h)
                x1 = int(j * w / out_w)
                x2 = int((j + 1) * w / out_w)
                result[i, j] = feature_map[y1:y2, x1:x2].mean(axis=(0, 1))
        return result.ravel()

    def save(self, path: str) -> None:
        """保存投影参数到 .npz 文件。"""
        if self._params is None:
            raise RuntimeError("No projection params to save")
        data: dict[str, np.ndarray] = {
            "weights": self._params.weights,
            "bias": self._params.bias,
            "input_keys": np.array(self._params.input_keys),
        }
        for key, size in self._params.pool_sizes.items():
            data[f"pool_{key}_h"] = np.array(size[0])
            data[f"pool_{key}_w"] = np.array(size[1])
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **data)

    @classmethod
    def load(cls, path: str) -> "EmbeddingProjector":
        """从 .npz 文件加载投影参数。"""
        data = np.load(path, allow_pickle=True)
        instance = cls()
        input_keys = list(data["input_keys"])
        pool_sizes: dict[str, tuple[int, int]] = {}
        for key in input_keys:
            h = int(data.get(f"pool_{key}_h", 1))
            w = int(data.get(f"pool_{key}_w", 1))
            pool_sizes[key] = (h, w)
        instance._params = ProjectionParams(
            weights=data["weights"].astype(np.float32),
            bias=data["bias"].astype(np.float32),
            pool_sizes=pool_sizes,
            input_keys=input_keys,
        )
        return instance

    @classmethod
    def fit(
        cls,
        features_list: list[dict[str, np.ndarray]],
        *,
        output_dim: int = 384,
        pool_sizes: Optional[dict[str, tuple[int, int]]] = None,
    ) -> "EmbeddingProjector":
        """用 PCA 初始化投影矩阵。

        从正常样本的多尺度特征计算 PCA 投影到 output_dim 维。
        pool_sizes 默认为全局平均池化 (1, 1)。
        """
        if not features_list:
            raise ValueError("features_list must not be empty")

        first = features_list[0]
        input_keys = sorted(k for k in first if isinstance(first[k], np.ndarray) and first[k].ndim >= 3)

        if pool_sizes is None:
            pool_sizes = {key: (1, 1) for key in input_keys}

        pooled_list = []
        instance = cls()
        for feats in features_list:
            pooled = []
            for key in input_keys:
                feat = feats.get(key)
                if feat is None:
                    raise KeyError(
                        f"Missing feature key '{key}' during PCA fit"
                    )
                else:
                    pooled.append(instance._adaptive_pool(feat, pool_sizes[key]))
            pooled_list.append(np.concatenate(pooled))

        X = np.stack(pooled_list, axis=0).astype(np.float64)  # (N, concat_dim)
        mean_vec = X.mean(axis=0)
        X_centered = X - mean_vec

        # PCA via SVD
        U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
        k = min(output_dim, X_centered.shape[1], X_centered.shape[0])
        weights = Vt[:k].T  # (concat_dim, output_dim)
        bias = -mean_vec @ weights

        instance._params = ProjectionParams(
            weights=weights.astype(np.float32),
            bias=bias.astype(np.float32),
            pool_sizes=pool_sizes,
            input_keys=input_keys,
        )
        return instance

    @property
    def is_fitted(self) -> bool:
        return self._params is not None

    @property
    def output_dim(self) -> int:
        if self._params is None:
            return 0
        return self._params.weights.shape[1]
