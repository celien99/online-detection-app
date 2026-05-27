from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BudgetScope(Enum):
    """Controls what the budget controller is allowed to throttle."""
    PROPOSAL = "proposal"
    PROPOSAL_AND_FILTER = "proposal_and_filter"
    FULL_PIPELINE = "full_pipeline"


@dataclass
class BudgetConfig:
    """Configuration for adaptive budget control."""
    enabled: bool = True
    scope: BudgetScope = BudgetScope.PROPOSAL_AND_FILTER
    target_latency_ms: float = 15.0
    hard_limit_ms: float = 20.0
    max_cc_before_emergency: int = 50
    avg_filter_latency_ms: float = 3.0
    window_size: int = 100
    threshold_multiplier_step: float = 0.5
    threshold_multiplier_max: float = 3.0
    recovery_rate: float = 0.01


@dataclass
class ProposalConfig:
    """Configuration for region proposal generation."""
    # Heatmap thresholding
    heatmap_threshold_mode: str = "adaptive"  # "adaptive" or "fixed"
    heatmap_threshold_fixed: float = 0.5
    heatmap_adaptive_std_multiplier: float = 1.5

    # Connected component filtering
    min_component_area: int = 16  # pixels
    min_solidity: float = 0.3
    max_proposals: int = 20

    # Morphological cleanup
    open_kernel_size: int = 3
    close_kernel_size: int = 5

    # Bounding box expansion
    context_padding_ratio: float = 0.10
    min_crop_size: int = 20

    # Aggregation
    aggregation_method: str = "weighted_confidence"
    area_exponent: float = 0.5
    confidence_threshold: float = 0.5
    budget: BudgetConfig | None = None


@dataclass
class CascadingBudgetConfig:
    """Configuration for cascading (proposal + filter) budget control."""
    enabled: bool = True

    # Proposal 阶段（复用现有 BudgetConfig）
    proposal: BudgetConfig = field(default_factory=BudgetConfig)

    # Filter 阶段
    filter_budget_ratio: float = 0.4       # Proposal 后最多 40% 时间给 Filter
    filter_hard_limit_ms: float = 8.0      # Filter 阶段硬上限
    filter_cost_ema_alpha: float = 0.95    # per-patch cost 的 EMA 系数
    filter_min_patches: int = 1            # 即使预算不够也最少送几个 patch

    # 紧急熔断
    emergency_filter_ratio: float = 0.1    # 剩余预算低于此比例触发 emergency
