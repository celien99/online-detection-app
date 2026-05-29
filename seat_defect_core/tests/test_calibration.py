"""Tests for calibration layer components."""

from __future__ import annotations

import numpy as np
import pytest

from seat_defect_core.calibration import (
    CalibrationConfig,
    CalibrationRegistry,
    CameraNormalizer,
    EMAFeatureCenter,
    EmbeddingProjector,
    ProjectionConfig,
    WhiteningConfig,
    WhiteningTransform,
)


class TestCameraNormalizer:
    def test_fit_and_normalize(self):
        rng = np.random.RandomState(42)
        normalizer = CameraNormalizer()
        features_list = []
        for _ in range(20):
            features_list.append({
                "teacher": rng.randn(8, 8, 384).astype(np.float32),
                "student": rng.randn(8, 8, 768).astype(np.float32),
                "difference": rng.randn(8, 8, 384).astype(np.float32),
            })

        normalizer.fit(features_list)
        assert normalizer.is_fitted

        normalized = normalizer.normalize(features_list[0])
        for key in ["teacher", "student", "difference"]:
            val = normalized[key]
            flat = val.reshape(-1, val.shape[-1])
            channel_mean = flat.mean(axis=0)
            channel_std = flat.std(axis=0)
            assert np.allclose(channel_mean, 0.0, atol=0.5)
            assert np.allclose(channel_std, 1.0, atol=0.5)

    def test_save_and_load(self, tmp_path):
        normalizer = CameraNormalizer()
        features_list = [{
            "teacher": np.random.randn(8, 8, 384).astype(np.float32),
            "student": np.random.randn(4, 4, 768).astype(np.float32),
            "difference": np.random.randn(8, 8, 384).astype(np.float32),
        }]
        normalizer.fit(features_list)

        path = str(tmp_path / "norm_stats.npz")
        normalizer.save(path)
        loaded = CameraNormalizer.load(path)
        assert loaded.is_fitted

        original = normalizer.normalize(features_list[0])
        reloaded = loaded.normalize(features_list[0])
        for key in original:
            assert np.allclose(original[key], reloaded[key], atol=1e-6)

    def test_online_update(self):
        normalizer = CameraNormalizer()
        feats = {
            "teacher": np.ones((8, 8, 384), dtype=np.float32) * 5.0,
            "student": np.ones((4, 4, 768), dtype=np.float32) * 5.0,
            "difference": np.ones((8, 8, 384), dtype=np.float32) * 5.0,
        }
        normalizer.update(feats)
        assert normalizer.is_fitted
        stats = normalizer._stats["teacher"]
        assert np.allclose(stats.mean, 5.0, atol=0.01)

    def test_missing_key_passthrough(self):
        normalizer = CameraNormalizer()
        features_list = [{
            "teacher": np.random.randn(4, 4, 384).astype(np.float32),
        }]
        normalizer.fit(features_list)

        # extra key (not in _FEATURE_KEYS) not included in normalize output
        result = normalizer.normalize({
            "teacher": np.random.randn(4, 4, 384).astype(np.float32),
            "extra_key": np.random.randn(2, 2, 64).astype(np.float32),
        })
        assert "teacher" in result
        assert "extra_key" not in result


class TestEmbeddingProjector:
    def test_fit_and_project(self):
        features_list = []
        for _ in range(100):
            features_list.append({
                "teacher": np.random.randn(8, 8, 384).astype(np.float32),
                "student": np.random.randn(4, 4, 768).astype(np.float32),
            })

        projector = EmbeddingProjector.fit(
            features_list,
            output_dim=64,
            pool_sizes={"teacher": (1, 1), "student": (1, 1)},
        )
        assert projector.is_fitted
        assert projector.output_dim == 64

        vec = projector.project(features_list[0])
        assert vec.shape == (64,)
        assert abs(np.linalg.norm(vec) - 1.0) < 0.01

    def test_missing_feature_raises(self):
        projector = EmbeddingProjector.fit(
            [{"teacher": np.random.randn(8, 8, 384).astype(np.float32)}],
            output_dim=32,
        )
        with pytest.raises(KeyError):
            projector.project({"wrong_key": np.random.randn(8, 8, 64).astype(np.float32)})

    def test_save_and_load(self, tmp_path):
        features_list = [{
            "teacher": np.random.randn(8, 8, 384).astype(np.float32),
        }]
        projector = EmbeddingProjector.fit(features_list, output_dim=32)

        path = str(tmp_path / "projector.npz")
        projector.save(path)
        loaded = EmbeddingProjector.load(path)

        v1 = projector.project(features_list[0])
        v2 = loaded.project(features_list[0])
        assert np.allclose(v1, v2, atol=1e-6)


class TestWhiteningTransform:
    def test_fit_and_whiten(self):
        rng = np.random.RandomState(42)
        base = rng.randn(100, 64).astype(np.float32)
        M = rng.randn(64, 64).astype(np.float32) * 0.3 + np.eye(64)
        correlated = base @ M.T
        correlated = correlated / np.linalg.norm(correlated, axis=1, keepdims=True)

        whitening = WhiteningTransform(dim=64)
        whitening.fit([correlated[i] for i in range(100)])

        whitened = whitening.whiten(correlated[0])
        assert whitened.shape == (64,)
        assert abs(np.linalg.norm(whitened) - 1.0) < 0.01

    def test_not_fitted_raises(self):
        whitening = WhiteningTransform(dim=64)
        with pytest.raises(RuntimeError):
            whitening.whiten(np.random.randn(64).astype(np.float32))

    def test_save_and_load(self, tmp_path):
        rng = np.random.RandomState(42)
        embeddings = rng.randn(50, 32).astype(np.float32)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        whitening = WhiteningTransform(dim=32)
        whitening.fit([embeddings[i] for i in range(50)])

        path = str(tmp_path / "whitening.npz")
        whitening.save(path)
        loaded = WhiteningTransform.load(path)

        w1 = whitening.whiten(embeddings[0])
        w2 = loaded.whiten(embeddings[0])
        assert np.allclose(w1, w2, atol=1e-6)


class TestEMAFeatureCenter:
    def test_update_and_query(self):
        ema = EMAFeatureCenter(alpha=0.9, dim=32)
        emb1 = np.ones(32, dtype=np.float32) / np.sqrt(32)
        emb2 = np.full(32, -0.5, dtype=np.float32)
        emb2 = emb2 / np.linalg.norm(emb2)

        ema.update("defect_A", emb1)
        ema.update("defect_B", emb2)

        nearest = ema.query_nearest(emb1, top_k=2)
        assert nearest[0][0] == "defect_A"
        assert nearest[0][1] < nearest[1][1]

    def test_is_novel(self):
        ema = EMAFeatureCenter(alpha=0.9, dim=32)
        emb = np.ones(32, dtype=np.float32) / np.sqrt(32)
        ema.update("defect_A", emb)

        similar = emb + np.random.randn(32).astype(np.float32) * 0.01
        similar = similar / np.linalg.norm(similar)
        assert not ema.is_novel(similar, threshold=0.3)

        novel = -emb
        assert ema.is_novel(novel, threshold=0.3)

    def test_save_and_load(self, tmp_path):
        ema = EMAFeatureCenter(alpha=0.9, dim=32)
        emb = np.ones(32, dtype=np.float32) / np.sqrt(32)
        ema.update("defect_A", emb)

        path = str(tmp_path / "centers.json")
        ema.save(path)
        loaded = EMAFeatureCenter.load(path)

        assert loaded.center_count() == 1
        assert loaded.list_types() == ["defect_A"]
        center = loaded.get_center("defect_A")
        assert np.allclose(center.center, emb, atol=1e-5)


class TestCalibrationRegistry:
    def test_calibrate_full_pipeline(self, tmp_path):
        # 1. 先在原始特征上拟合 normalizer（per-camera per-channel 标准化）
        normalizer = CameraNormalizer()
        raw_feats_list = []
        for _ in range(100):
            raw_feats_list.append({
                "teacher": np.random.randn(8, 8, 384).astype(np.float32),
                "student": np.random.randn(4, 4, 768).astype(np.float32),
                "difference": np.random.randn(8, 8, 384).astype(np.float32),
            })
        normalizer.fit(raw_feats_list)
        norm_path = str(tmp_path / "norm.npz")
        normalizer.save(norm_path)

        # 2. 在归一化特征上拟合 projector（正确顺序：先 normalize 再 project）
        proj_feats = []
        for _ in range(500):
            raw = {
                "teacher": np.random.randn(8, 8, 384).astype(np.float32),
                "student": np.random.randn(4, 4, 768).astype(np.float32),
                "difference": np.random.randn(8, 8, 384).astype(np.float32),
            }
            proj_feats.append(normalizer.normalize(raw))
        projector = EmbeddingProjector.fit(proj_feats, output_dim=384)
        proj_path = str(tmp_path / "proj.npz")
        projector.save(proj_path)

        config = CalibrationConfig(
            projection=ProjectionConfig(enabled=True, projector_path=proj_path),
            whitening=WhiteningConfig(enabled=False),
            camera_norm_paths={"cam_front": norm_path},
        )
        registry = CalibrationRegistry(config)

        feats = {
            "teacher": np.random.randn(8, 8, 384).astype(np.float32),
            "student": np.random.randn(4, 4, 768).astype(np.float32),
            "difference": np.random.randn(8, 8, 384).astype(np.float32),
        }
        result = registry.calibrate("cam_front", feats)
        assert result is not None
        assert len(result.vector) == 384
        assert result.contract_version == "1.0.0"
        assert result.source == "efficientad_projected"

    def test_calibrate_disabled(self):
        config = CalibrationConfig(enabled=False)
        registry = CalibrationRegistry(config)
        assert registry.calibrate("any", {}) is None
