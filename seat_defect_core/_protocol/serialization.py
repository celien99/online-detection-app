from __future__ import annotations

import json
from typing import Any

from .entities import (
    AnomalyContext,
    BoundingBox,
    EfficientADFeatures,
    FilterResult,
    ImageRef,
    PatchProposal,
    ProposalMetadata,
    ROIContext,
)


def _bbox_to_dict(b: BoundingBox) -> dict[str, float]:
    return {"x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2}


def _bbox_from_dict(d: dict[str, float]) -> BoundingBox:
    return BoundingBox(x1=d["x1"], y1=d["y1"], x2=d["x2"], y2=d["y2"])


def _image_ref_to_dict(r: ImageRef) -> dict[str, Any]:
    return {"key": r.key, "width": r.width, "height": r.height}


def _image_ref_from_dict(d: dict[str, Any]) -> ImageRef:
    return ImageRef(key=d["key"], width=d.get("width", 0), height=d.get("height", 0))


def _roi_context_to_dict(r: ROIContext) -> dict[str, Any]:
    return {
        "roi_bbox": _bbox_to_dict(r.roi_bbox),
        "roi_image_ref": _image_ref_to_dict(r.roi_image_ref),
        "roi_size": list(r.roi_size),
    }


def _roi_context_from_dict(d: dict[str, Any]) -> ROIContext:
    return ROIContext(
        roi_bbox=_bbox_from_dict(d["roi_bbox"]),
        roi_image_ref=_image_ref_from_dict(d["roi_image_ref"]),
        roi_size=(d["roi_size"][0], d["roi_size"][1]),
    )


def _anomaly_context_to_dict(a: AnomalyContext) -> dict[str, Any]:
    return {
        "anomaly_score": a.anomaly_score,
        "anomaly_threshold": a.anomaly_threshold,
        "heatmap_ref": _image_ref_to_dict(a.heatmap_ref),
        "feature_ref": a.feature_ref,
    }


def _anomaly_context_from_dict(d: dict[str, Any]) -> AnomalyContext:
    return AnomalyContext(
        anomaly_score=d["anomaly_score"],
        anomaly_threshold=d["anomaly_threshold"],
        heatmap_ref=_image_ref_from_dict(d["heatmap_ref"]),
        feature_ref=d["feature_ref"],
    )


def _features_to_dict(f: EfficientADFeatures) -> dict[str, Any]:
    return {
        "teacher_l1_ref": f.teacher_l1_ref,
        "teacher_l2_ref": f.teacher_l2_ref,
        "teacher_l3_ref": f.teacher_l3_ref,
        "difference_ref": f.difference_ref,
        "teacher_l1_shape": list(f.teacher_l1_shape),
        "teacher_l2_shape": list(f.teacher_l2_shape),
        "teacher_l3_shape": list(f.teacher_l3_shape),
        "difference_shape": list(f.difference_shape),
    }


def _features_from_dict(d: dict[str, Any]) -> EfficientADFeatures:
    return EfficientADFeatures(
        teacher_l1_ref=d["teacher_l1_ref"],
        teacher_l2_ref=d["teacher_l2_ref"],
        teacher_l3_ref=d["teacher_l3_ref"],
        difference_ref=d["difference_ref"],
        teacher_l1_shape=tuple(d["teacher_l1_shape"]),
        teacher_l2_shape=tuple(d["teacher_l2_shape"]),
        teacher_l3_shape=tuple(d["teacher_l3_shape"]),
        difference_shape=tuple(d["difference_shape"]),
    )


def _proposal_meta_to_dict(m: ProposalMetadata) -> dict[str, Any]:
    return {
        "component_area": m.component_area,
        "component_solidity": m.component_solidity,
        "rank": m.rank,
        "total_proposals": m.total_proposals,
        "generation_params": m.generation_params,
    }


def _proposal_meta_from_dict(d: dict[str, Any]) -> ProposalMetadata:
    return ProposalMetadata(
        component_area=d["component_area"],
        component_solidity=d["component_solidity"],
        rank=d["rank"],
        total_proposals=d["total_proposals"],
        generation_params=d.get("generation_params", {}),
    )


def _filter_result_to_dict(f: FilterResult) -> dict[str, Any]:
    return {
        "is_real_defect": f.is_real_defect,
        "confidence": f.confidence,
        "real_defect_score": f.real_defect_score,
        "false_alarm_score": f.false_alarm_score,
        "class_id": f.class_id,
        "diagnostics": f.diagnostics,
    }


def _filter_result_from_dict(d: dict[str, Any]) -> FilterResult:
    return FilterResult(
        is_real_defect=d["is_real_defect"],
        confidence=d["confidence"],
        real_defect_score=d["real_defect_score"],
        false_alarm_score=d["false_alarm_score"],
        class_id=d["class_id"],
        diagnostics=d.get("diagnostics", {}),
    )


def proposal_to_dict(p: PatchProposal) -> dict[str, Any]:
    result: dict[str, Any] = {
        "proposal_id": p.proposal_id,
        "isolation_key": p.isolation_key,
        "source_roi": _roi_context_to_dict(p.source_roi),
        "patch_image": _image_ref_to_dict(p.patch_image),
        "patch_bbox": _bbox_to_dict(p.patch_bbox),
        "anomaly_context": _anomaly_context_to_dict(p.anomaly_context),
        "efficientad_features": _features_to_dict(p.efficientad_features),
        "proposal_metadata": _proposal_meta_to_dict(p.proposal_metadata),
    }
    if p.filter_result is not None:
        result["filter_result"] = _filter_result_to_dict(p.filter_result)
    return result


def proposal_from_dict(d: dict[str, Any]) -> PatchProposal:
    filter_result = None
    if "filter_result" in d and d["filter_result"] is not None:
        filter_result = _filter_result_from_dict(d["filter_result"])
    return PatchProposal(
        proposal_id=d["proposal_id"],
        isolation_key=d["isolation_key"],
        source_roi=_roi_context_from_dict(d["source_roi"]),
        patch_image=_image_ref_from_dict(d["patch_image"]),
        patch_bbox=_bbox_from_dict(d["patch_bbox"]),
        anomaly_context=_anomaly_context_from_dict(d["anomaly_context"]),
        efficientad_features=_features_from_dict(d["efficientad_features"]),
        proposal_metadata=_proposal_meta_from_dict(d["proposal_metadata"]),
        filter_result=filter_result,
    )


def proposals_to_json(proposals: list[PatchProposal]) -> str:
    return json.dumps([proposal_to_dict(p) for p in proposals], ensure_ascii=False)


def proposals_from_json(json_str: str) -> list[PatchProposal]:
    return [proposal_from_dict(d) for d in json.loads(json_str)]
