"""轻量级规则引擎，在 Filter Classifier 之后、Fusion 之前执行。

支持两类规则：
1. 阈值规则（手工配置）：基于 anomaly_score、patch_count 等统计量的误报过滤
2. 知识规则（离线平台部署）：基于 camera_id、defect_type 等的业务决策规则

多条规则同时命中时，取最高优先级的 action（escalate > flag > suppress_to_ok > ignore）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from .config import RuleConfig
from .core_types import CameraInspectionResult


def apply_rules(
    result: CameraInspectionResult,
    rules: List[RuleConfig],
) -> CameraInspectionResult:
    """对单机位检测结果应用规则引擎后处理。

    与旧版本不同：匹配所有规则后取最高优先级的 action，而非命中即停止。
    """
    if result.status != "NG":
        return result

    matched: List[RuleConfig] = []
    for rule in rules:
        if not rule.enabled:
            continue
        if _rule_matches(result, rule):
            matched.append(rule)

    if not matched:
        return result

    # 取最高优先级的 action
    best = max(matched, key=lambda r: r.priority)

    if best.action == "suppress_to_ok":
        result.status = "OK"
        result.reason = f"rule_{best.name}"
    elif best.action == "ignore":
        # 同 suppress_to_ok：离线知识标记为"忽略"的缺陷
        result.status = "OK"
        result.reason = f"rule_{best.name}"
    elif best.action == "flag_for_review":
        result.reason = f"ng_flagged_{best.name}"
    elif best.action == "escalate":
        result.reason = f"ng_escalated_{best.name}"

    return result


def _rule_matches(result: CameraInspectionResult, rule: RuleConfig) -> bool:
    """检查检测结果是否匹配规则的所有条件。"""
    texture = result.texture_result
    filter_r = result.filter_result

    # ── 离线知识条件 ──
    # 机位过滤
    if rule.camera_id is not None and rule.camera_id != result.camera_id:
        return False

    # 缺陷类型过滤（需 Filter Classifier 支持多分类输出；当前为二进制分类器，
    # filter_result 无 defect_type 字段，此条件在扩展前不会命中）
    if rule.defect_type is not None:
        defect_type = getattr(filter_r, "defect_type", None) if filter_r is not None else None
        if defect_type != rule.defect_type:
            return False

    # Filter Classifier 置信度范围
    if rule.min_classifier_confidence is not None:
        if filter_r is None or filter_r.confidence < rule.min_classifier_confidence:
            return False
    if rule.max_classifier_confidence is not None:
        if filter_r is None or filter_r.confidence > rule.max_classifier_confidence:
            return False

    # ── 阈值条件 ──
    # 要求 Filter Classifier 判定为真实缺陷
    if rule.require_filter_real_defect:
        if filter_r is None or not filter_r.is_real_defect:
            return False

    # 要求 Filter Classifier 判定为误报
    if rule.require_filter_false_alarm:
        if filter_r is None or filter_r.is_real_defect:
            return False

    # 异常分数低于阈值
    if rule.max_anomaly_score is not None:
        if texture is None or texture.score >= rule.max_anomaly_score:
            return False

    # 强异常 patch 数低于阈值
    if rule.min_strong_patch_count is not None:
        if texture is None or texture.strong_patch_count >= rule.min_strong_patch_count:
            return False

    # 强异常 patch 比例低于阈值
    if rule.max_strong_patch_ratio is not None:
        if texture is None or texture.strong_patch_ratio >= rule.max_strong_patch_ratio:
            return False

    return True


def load_deployed_rules(path: str) -> List[RuleConfig]:
    """从离线平台部署的 JSON 文件加载知识规则。"""
    rules_json = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rules_json, list):
        raise TypeError(f"规则文件顶层必须是数组：{path}")

    rules: List[RuleConfig] = []
    for item in rules_json:
        rules.append(RuleConfig(
            name=item.get("name", "deployed_rule"),
            enabled=item.get("enabled", True),
            camera_id=item.get("camera_id"),
            defect_type=item.get("defect_type"),
            min_classifier_confidence=item.get("min_classifier_confidence"),
            max_classifier_confidence=item.get("max_classifier_confidence"),
            max_anomaly_score=item.get("max_anomaly_score"),
            min_strong_patch_count=item.get("min_strong_patch_count"),
            max_strong_patch_ratio=item.get("max_strong_patch_ratio"),
            require_filter_false_alarm=item.get("require_filter_false_alarm", False),
            require_filter_real_defect=item.get("require_filter_real_defect", False),
            action=item.get("action", "flag_for_review"),
            source=item.get("source", "offline_platform"),
            knowledge_entry_id=item.get("knowledge_entry_id"),
            priority=item.get("priority", 0),
        ))
    return rules


def merge_rules(
    local_rules: List[RuleConfig],
    deployed_rules_path: Optional[str] = None,
) -> List[RuleConfig]:
    """合并本地配置规则和离线平台部署规则。

    部署规则优先级通常更高（priority 更大），排在前面。
    """
    if deployed_rules_path and Path(deployed_rules_path).exists():
        deployed = load_deployed_rules(deployed_rules_path)
        # 部署规则优先，按 priority 降序
        return sorted(deployed + list(local_rules), key=lambda r: r.priority, reverse=True)
    return list(local_rules)


__all__ = [
    "RuleConfig",
    "apply_rules",
    "load_deployed_rules",
    "merge_rules",
]
