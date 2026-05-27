"""ZCA / PCA whitening for unified embeddings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

_logger = logging.getLogger(__name__)


class WhiteningTransform:
    """ZCA 白化变换：W = U @ diag(1/sqrt(S + eps)) @ U^T

    在 EmbeddingProjector 之后使用，消除 embedding 维度间的相关性，
    使各维度等方差。只有在统一嵌入空间中白化矩阵才有意义（维度固定，语义对齐）。

    在正常样本的 embedding 上拟合，推理时应用固定矩阵变换。
    """

    def __init__(self, dim: int = 384, regularization: float = 1e-4):
        self._dim = dim
        self._regularization = regularization
        self._W: Optional[np.ndarray] = None  # (dim, dim) whitening matrix
        self._mean: Optional[np.ndarray] = None  # (dim,) embedding mean

    def fit(self, embeddings: list[np.ndarray]) -> None:
        """在正常样本 embedding 上计算 ZCA 白化矩阵。

        Args:
            embeddings: 384-dim L2 归一化向量的列表
        """
        X = np.stack(embeddings, axis=0).astype(np.float64)  # (N, dim)
        self._mean = X.mean(axis=0).astype(np.float32)

        X_centered = X - self._mean.astype(np.float64)
        cov = (X_centered.T @ X_centered) / (X.shape[0] - 1)

        # SVD of covariance matrix
        U, S, _ = np.linalg.svd(cov)
        # ZCA: W = U @ diag(1/sqrt(S + eps)) @ U^T
        inv_sqrt = np.diag(1.0 / np.sqrt(S + self._regularization))
        self._W = (U @ inv_sqrt @ U.T).astype(np.float32)

    def whiten(self, embedding: np.ndarray) -> np.ndarray:
        """对单个 embedding 向量应用白化变换。

        Returns:
            白化后的 (dim,) float32 向量
        """
        if self._W is None or self._mean is None:
            raise RuntimeError("WhiteningTransform not fitted")
        x = np.asarray(embedding, dtype=np.float32) - self._mean
        whitened = x @ self._W
        norm = np.linalg.norm(whitened)
        if norm > 1e-8:
            whitened = whitened / norm
        else:
            _logger.warning(
                "whitening_near_zero_norm",
                extra={"norm": float(norm)},
            )
        return whitened.astype(np.float32)

    def whiten_batch(self, embeddings: np.ndarray) -> np.ndarray:
        """批量白化。embeddings shape: (N, dim)"""
        if self._W is None or self._mean is None:
            raise RuntimeError("WhiteningTransform not fitted")
        x = np.asarray(embeddings, dtype=np.float32) - self._mean.astype(np.float32)
        whitened = x @ self._W
        norms = np.linalg.norm(whitened, axis=1, keepdims=True)
        near_zero = (norms < 1e-8).sum()
        if near_zero > 0:
            _logger.warning(
                "whitening_batch_near_zero_norm",
                extra={"near_zero_count": int(near_zero), "batch_size": len(embeddings)},
            )
        norms = np.where(norms < 1e-8, 1.0, norms)
        return (whitened / norms).astype(np.float32)

    def save(self, path: str) -> None:
        """保存白化矩阵到 .npz 文件。"""
        if self._W is None or self._mean is None:
            raise RuntimeError("WhiteningTransform not fitted")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, W=self._W, mean=self._mean, dim=self._dim)

    @classmethod
    def load(cls, path: str) -> "WhiteningTransform":
        """从 .npz 文件加载白化矩阵。"""
        data = np.load(path)
        dim = int(data["dim"])
        W = data["W"]
        mean_arr = data["mean"]
        assert W.shape == (dim, dim), f"W shape mismatch: expected ({dim},{dim}), got {W.shape}"
        assert mean_arr.shape == (dim,), f"mean shape mismatch: expected ({dim},), got {mean_arr.shape}"
        instance = cls(dim=dim)
        instance._W = W.astype(np.float32)
        instance._mean = mean_arr.astype(np.float32)
        return instance

    @property
    def is_fitted(self) -> bool:
        return self._W is not None and self._mean is not None
