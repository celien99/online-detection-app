from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .entities import FilterResult


@dataclass
class CanonicalPatchProposal:
    """Strictly-validated canonical schema for patch proposals. Zero data drift."""

    # 不变标识（生成后不可修改）
    proposal_id: str
    isolation_key: str

    # 空间参照（归一化坐标系 0-1，漂移免疫）
    roi_bbox_norm: tuple[float, float, float, float]
    patch_bbox_norm: tuple[float, float, float, float]
    roi_size_px: tuple[int, int]  # 实际像素尺寸（用于反归一化）

    # 异常上下文
    anomaly_score: float
    component_area_px: int
    component_solidity: float

    # 引用（不存二进制数据）
    patch_image_ref: str  # MinIO key
    heatmap_ref: str
    feature_ref: str  # .npy base path

    # Schema 版本
    schema_version: str = "1.0.0"

    # 运行时追踪（在线填充）
    identity_id: Optional[str] = None
    filter_result: Optional[FilterResult] = None
    unified_embedding: Optional[list[float]] = None

    # 生成参数快照（可复现性）
    generation_params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate invariants on construction."""
        x1, y1, x2, y2 = self.patch_bbox_norm
        assert 0 <= x1 < x2 <= 1, f"patch_bbox_norm x invalid: {self.patch_bbox_norm}"
        assert 0 <= y1 < y2 <= 1, f"patch_bbox_norm y invalid: {self.patch_bbox_norm}"
        assert self.component_area_px > 0, f"component_area_px must be > 0"
        assert len(self.roi_size_px) == 2
        assert self.roi_size_px[0] > 0 and self.roi_size_px[1] > 0

    def patch_bbox_px(self) -> tuple[int, int, int, int]:
        """Convert normalized bbox to pixel coordinates."""
        w, h = self.roi_size_px
        x1, y1, x2, y2 = self.patch_bbox_norm
        return (int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h))

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "proposal_id": self.proposal_id,
            "schema_version": self.schema_version,
            "isolation_key": self.isolation_key,
            "roi_bbox_norm": list(self.roi_bbox_norm),
            "patch_bbox_norm": list(self.patch_bbox_norm),
            "roi_size_px": list(self.roi_size_px),
            "anomaly_score": self.anomaly_score,
            "component_area_px": self.component_area_px,
            "component_solidity": self.component_solidity,
            "patch_image_ref": self.patch_image_ref,
            "heatmap_ref": self.heatmap_ref,
            "feature_ref": self.feature_ref,
            "generation_params": self.generation_params,
        }
        if self.identity_id is not None:
            d["identity_id"] = self.identity_id
        if self.filter_result is not None:
            from .serialization import _filter_result_to_dict

            d["filter_result"] = _filter_result_to_dict(self.filter_result)
        if self.unified_embedding is not None:
            d["unified_embedding"] = self.unified_embedding
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CanonicalPatchProposal":
        from .serialization import _filter_result_from_dict

        fr = None
        if "filter_result" in d and d["filter_result"] is not None:
            fr = _filter_result_from_dict(d["filter_result"])
        return cls(
            proposal_id=d["proposal_id"],
            schema_version=d.get("schema_version", "1.0.0"),
            isolation_key=d["isolation_key"],
            roi_bbox_norm=tuple(d["roi_bbox_norm"]),
            patch_bbox_norm=tuple(d["patch_bbox_norm"]),
            roi_size_px=tuple(d["roi_size_px"]),
            anomaly_score=d["anomaly_score"],
            component_area_px=d["component_area_px"],
            component_solidity=d["component_solidity"],
            patch_image_ref=d["patch_image_ref"],
            heatmap_ref=d["heatmap_ref"],
            feature_ref=d["feature_ref"],
            identity_id=d.get("identity_id"),
            filter_result=fr,
            unified_embedding=d.get("unified_embedding"),
            generation_params=d.get("generation_params", {}),
        )
