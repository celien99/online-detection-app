"""Per-camera per-channel feature normalization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class CameraNormStats:
    """Per-channel mean/std for a single feature key."""
    mean: np.ndarray  # shape matches feature channels
    std: np.ndarray
    sample_count: int = 0
    def to_dict(self) -> dict:
        return {
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "sample_count": self.sample_count,
        }


class CameraNormalizer:
    """Per-camera per-channel (x - mean) / std normalization for EfficientAD features.

    每个 (camera_id, model_path) 对应一组独立的 stats。
    四个特征 key 各存一组：teacher_l1, teacher_l2, teacher_l3, difference。

    离线拟合：在正常样本（is_anomaly=False）的特征上调用 fit()。
    推理时：调用 normalize() 查表应用，零额外开销。
    """

    _FEATURE_KEYS = ("teacher_l1", "teacher_l2", "teacher_l3", "difference")

    def __init__(self):
        self._stats: dict[str, CameraNormStats] = {}

    def fit(self, features_list: list[dict[str, np.ndarray]]) -> None:
        """在正常样本特征列表上离线拟合 per-channel mean/std。

        将所有样本特征 concatenate 到内存中计算 mean/std，
        大规模数据集注意 O(n) 内存占用。

        Args:
            features_list: 正常样本的特征字典列表，每个字典含 'teacher_l1' 等 key，
                          每个 value 是 (H, W, C) 或 (C,) 的 numpy 数组。
        """
        accumulators: dict[str, list[np.ndarray]] = {key: [] for key in self._FEATURE_KEYS}
        for feats in features_list:
            for key in self._FEATURE_KEYS:
                val = feats.get(key)
                if val is not None:
                    if val.ndim >= 3:
                        flat = val.reshape(-1, val.shape[-1]).astype(np.float64)
                    elif val.ndim == 2:
                        flat = val.astype(np.float64)
                    else:
                        flat = val.reshape(1, -1).astype(np.float64)
                    accumulators[key].append(flat)

        for key in self._FEATURE_KEYS:
            samples = accumulators[key]
            if not samples:
                continue
            all_data = np.concatenate(samples, axis=0)
            mean = all_data.mean(axis=0)
            std = all_data.std(axis=0)
            std = np.where(std < 1e-8, 1.0, std)
            self._stats[key] = CameraNormStats(
                mean=mean.astype(np.float32),
                std=std.astype(np.float32),
                sample_count=all_data.shape[0],
            )

    def normalize(self, features: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """对特征做 per-channel 标准化。缺失 key 保持原值。"""
        result: dict[str, np.ndarray] = {}
        for key in self._FEATURE_KEYS:
            val = features.get(key)
            if val is None:
                continue
            stats = self._stats.get(key)
            if stats is None:
                result[key] = val.copy()
            else:
                result[key] = (np.asarray(val, dtype=np.float32) - stats.mean) / stats.std
        return result

    def update(self, features: dict[str, np.ndarray]) -> None:
        """在线增量更新 stats（Welford 算法）。仅在正常判定时调用。"""
        for key in self._FEATURE_KEYS:
            val = features.get(key)
            if val is None:
                continue
            if val.ndim >= 3:
                samples = val.reshape(-1, val.shape[-1]).astype(np.float64)
            elif val.ndim == 2:
                samples = val.astype(np.float64)
            else:
                samples = val.reshape(1, -1).astype(np.float64)

            batch_mean = samples.mean(axis=0)
            batch_count = samples.shape[0]

            existing = self._stats.get(key)
            if existing is None:
                self._stats[key] = CameraNormStats(
                    mean=batch_mean.astype(np.float32),
                    std=samples.std(axis=0).astype(np.float32),
                    sample_count=batch_count,
                )
                continue

            # 使用 float64 中间计算保持精度
            old_mean = existing.mean.astype(np.float64)
            old_var = (existing.std.astype(np.float64)) ** 2
            delta = batch_mean - old_mean
            new_count = existing.sample_count + batch_count
            existing.mean = (old_mean + delta * batch_count / new_count).astype(np.float32)
            combined_var = (
                old_var * existing.sample_count
                + samples.var(axis=0) * batch_count
                + delta ** 2 * existing.sample_count * batch_count / new_count
            ) / new_count
            existing.std = np.sqrt(combined_var).astype(np.float32)
            existing.std = np.where(existing.std < 1e-8, 1.0, existing.std)
            existing.sample_count = new_count

    def save(self, path: str) -> None:
        """保存 stats 到 .npz 文件。"""
        data: dict[str, np.ndarray] = {}
        for key, stats in self._stats.items():
            data[f"{key}_mean"] = stats.mean
            data[f"{key}_std"] = stats.std
            data[f"{key}_count"] = np.array(stats.sample_count)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **data)

    @classmethod
    def load(cls, path: str) -> "CameraNormalizer":
        """从 .npz 文件加载 stats。"""
        data = np.load(path)
        normalizer = cls()
        for key in cls._FEATURE_KEYS:
            mean_key = f"{key}_mean"
            if mean_key in data:
                normalizer._stats[key] = CameraNormStats(
                    mean=data[mean_key].astype(np.float32),
                    std=data[f"{key}_std"].astype(np.float32),
                    sample_count=int(data.get(f"{key}_count", 0)),
                )
        return normalizer

    @property
    def is_fitted(self) -> bool:
        return set(self._stats.keys()) == set(self._FEATURE_KEYS)

    @property
    def fitted_keys(self) -> list[str]:
        return list(self._stats.keys())
