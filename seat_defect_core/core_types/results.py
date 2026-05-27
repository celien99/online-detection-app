"""主检测流程输出结果类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .geometry import BoundingBox
from .pipeline import DetectionResult, ImageQualityDecision


@dataclass
class TextureAnomalyResult:
    """纹理异常检测分支输出。"""

    score: float
    """图像级异常分数 (0-1)。"""

    threshold: float
    """异常判定阈值。"""

    is_anomaly: bool
    """是否判定为异常。"""

    heatmap: Any
    """ROI 坐标系下的异常热力图。"""

    anomaly_map: Any
    """模型原始输出异常图。"""

    valid_pixel_ratio: float = 1.0
    """ROI 内有效像素比例。"""

    features: Optional[dict[str, Any]] = None  # EfficientAD intermediate features

    strong_patch_count: int = 0
    """强异常 patch 数（高于阈值的连通域数量）。"""

    strong_patch_ratio: float = 0.0
    """强异常 patch 比例（强异常面积 / ROI 总面积）。"""


@dataclass
class InspectionError:
    """结构化错误，供外部系统稳定识别。"""

    code: str
    """稳定错误码。"""

    message: str
    """面向日志/调试的错误信息。"""

    stage: str
    """错误发生阶段。"""


@dataclass
class FilterClassifierResult:
    """过滤器分类器分支输出。"""

    is_real_defect: bool
    """分类器是否判定为真实缺陷（True=保留NG, False=误报应抑制）。"""

    confidence: float
    """预测类别的 softmax 置信度。"""

    real_defect_score: float
    """real_defect 类的 softmax 输出。"""

    false_alarm_score: float
    """false_alarm 类的 softmax 输出。"""

    class_id: int
    """预测类别ID：1=real_defect, 0=false_alarm。"""

    diagnostics: Dict[str, float | str] = field(default_factory=dict)
    """推理诊断指标（延迟、预处理时间、模式标签等）。"""


@dataclass
class CameraInspectionResult:
    """单机位最终检测结果。"""

    camera_id: str
    """机位 ID。"""

    frame_id: str
    """帧编号。"""

    source: str
    """输入来源标识。"""

    source_kind: str
    """输入来源类型。"""

    status: str
    """单机位状态：OK / NG / REJECT。"""

    reason: str
    """单机位状态原因。"""

    seat_model_id: Optional[str] = None
    """本次检测使用的座椅型号 ID。"""

    quality: Optional[ImageQualityDecision] = None
    """图像质量判定结果。"""

    detection: Optional[DetectionResult] = None
    """YOLO 检测结果。"""

    texture_result: Optional[TextureAnomalyResult] = None
    """纹理异常检测结果。"""

    filter_result: Optional[FilterClassifierResult] = None
    """过滤器分类器分支结果。"""

    proposals: list[Any] = field(default_factory=list)  # list[PatchProposal]
    """PatchCore 级别候选异常 patch 列表。"""

    crop_box: Optional[BoundingBox] = None
    """原图坐标系下最终使用的 ROI 裁剪框。"""

    artifact_paths: Dict[str, str] = field(default_factory=dict)
    """该机位关联的调试产物路径。"""

    timings_ms: Dict[str, float] = field(default_factory=dict)
    """该机位各阶段耗时，单位毫秒。"""

    error: Optional[InspectionError] = None
    """该机位结构化错误。"""

    overlay_image: Optional[Any] = field(default=None, repr=False, compare=False)
    """叠加了异常热力图的 BGR 调试图片，供调用方直接消费。"""

    original_image: Optional[Any] = field(default=None, repr=False, compare=False)
    """本次检测输入的原始 BGR 图像，供 NG 上传链路使用。"""

    roi_image: Optional[Any] = field(default=None, repr=False, compare=False)
    """原始 ROI 裁剪图像（未缩放到标准画布），供离线平台展示使用。"""

    roi_aligned_image: Optional[Any] = field(default=None, repr=False, compare=False)
    """标准 ROI 对齐图像 (BGR)，不含热力图叠加，供上传离线平台使用。"""

    _uploaded_identities: Optional[set[str]] = field(default=None, repr=False, compare=False)
    """已上传的身份 ID 集合，供 anomaly_uploader 内部使用。"""


@dataclass
class InspectionResult:
    """多机位融合后的整件检测结果。"""

    part_id: str
    """工件编号。"""

    frame_id: str
    """本次检测批次帧编号。"""

    timestamp: str
    """本次检测时间戳。"""

    status: str
    """整件状态：OK / NG / REJECT。"""

    decision_reason: str
    """整件融合判定原因。"""

    seat_model_id: Optional[str] = None
    """本次检测使用的座椅型号 ID。"""

    camera_results: List[CameraInspectionResult] = field(default_factory=list)
    """所有机位检测结果。"""

    timings_ms: Dict[str, float] = field(default_factory=dict)
    """整件检测各阶段耗时，单位毫秒。"""


@dataclass
class InspectionResponse:
    """core 对外返回的检测响应。"""

    result: InspectionResult
    """完整检测结果对象。"""

    report_path: str
    """最新检测报告 JSON 路径。"""

    artifact_paths: Dict[str, Dict[str, str]]
    """按机位聚合的调试产物路径。"""

    @property
    def status(self) -> str:
        """整件状态快捷访问。"""
        return self.result.status

    @property
    def decision_reason(self) -> str:
        """整件判定原因快捷访问。"""
        return self.result.decision_reason

    @property
    def part_id(self) -> str:
        """工件编号快捷访问。"""
        return self.result.part_id

    @property
    def seat_model_id(self) -> Optional[str]:
        """座椅型号 ID 快捷访问。"""
        return self.result.seat_model_id

    def to_dict(self) -> Dict[str, Any]:
        """转换为适合外部系统序列化的字典。"""
        from ..serialization import inspection_result_to_dict

        payload = inspection_result_to_dict(self.result)
        payload.update(
            {
                "report_path": self.report_path,
                "artifact_paths": self.artifact_paths,
            }
        )
        return payload


__all__ = [
    "CameraInspectionResult",
    "FilterClassifierResult",
    "InspectionError",
    "InspectionResponse",
    "InspectionResult",
    "TextureAnomalyResult",
]
