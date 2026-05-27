from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from .config import BudgetConfig, BudgetScope


@dataclass
class BudgetState:
    """Mutable state tracked across frames for budget control."""
    multiplier: float = 1.5
    recent_cc_counts: list[int] = field(default_factory=list)
    recent_latencies_ms: list[float] = field(default_factory=list)
    emergency_count: int = 0


class BudgetController:
    """Adaptive budget controller with three-mode operation."""

    def __init__(self, config: BudgetConfig | None = None):
        self.config = config or BudgetConfig()
        self._state = BudgetState()
        self._frame_start: float = 0.0

    def start_frame(self) -> None:
        self._frame_start = time.perf_counter()

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._frame_start) * 1000.0

    def remaining_budget_ms(self) -> float:
        return max(0.0, self.config.target_latency_ms - self.elapsed_ms())

    def regulate(self, heatmap: np.ndarray) -> tuple[float, int, str]:
        """Determine adaptive threshold and K limit for this frame.
        Returns: (threshold_value, max_proposals, mode_string)
        """
        cfg = self.config
        if not cfg.enabled:
            return (0.0, 999, "disabled")

        elapsed = self.elapsed_ms()
        self._state.recent_latencies_ms.append(elapsed)
        if len(self._state.recent_latencies_ms) > cfg.window_size:
            self._state.recent_latencies_ms.pop(0)

        # Emergency check
        cc_estimate = self._estimate_cc_count(heatmap)
        if elapsed >= cfg.hard_limit_ms or cc_estimate >= cfg.max_cc_before_emergency:
            self._state.emergency_count += 1
            return (0.99, 0, "emergency")

        # Optimization: slow adjustment based on history
        if len(self._state.recent_cc_counts) >= cfg.window_size:
            avg_cc = sum(self._state.recent_cc_counts[-cfg.window_size:]) / cfg.window_size
            if avg_cc > 20:
                self._state.multiplier = min(
                    cfg.threshold_multiplier_max,
                    self._state.multiplier + cfg.threshold_multiplier_step,
                )
            else:
                self._state.multiplier = max(
                    1.0,
                    self._state.multiplier - cfg.recovery_rate,
                )

        # Adaptive threshold
        h_mean = float(heatmap.mean())
        h_std = float(heatmap.std())
        base = h_mean + self._state.multiplier * h_std
        budget_factor = min(1.0, self.remaining_budget_ms() / cfg.target_latency_ms)
        threshold = base + (1.0 - budget_factor) * h_std

        # Dynamic K
        k = max(1, int(self.remaining_budget_ms() / cfg.avg_filter_latency_ms))

        return (threshold, k, "normal")

    def record_cc_count(self, count: int) -> None:
        self._state.recent_cc_counts.append(count)
        if len(self._state.recent_cc_counts) > self.config.window_size:
            self._state.recent_cc_counts.pop(0)

    def _estimate_cc_count(self, heatmap: np.ndarray) -> int:
        """Fast estimate: count pixels above a low threshold as an upper bound."""
        low_thresh = heatmap.mean() + 0.5 * heatmap.std()
        return int((heatmap > low_thresh).sum() / 16)


@dataclass
class FilterBudgetState:
    """Filter 阶段的预算追踪状态。"""
    estimated_cost_per_patch_ms: float = 3.0  # 初始估计
    recent_costs_ms: list[float] = field(default_factory=list)
    skip_count: int = 0
    emergency_skip_count: int = 0


class CascadingBudgetController:
    """两级预算控制器：Proposal + Filter 级联。

    包装现有的 BudgetController，新增 Filter 阶段的预算感知。
    schedule_filter() 根据剩余预算动态决定哪些 proposal 送 Filter。
    """

    def __init__(self, config: CascadingBudgetConfig | None = None):
        from .config import CascadingBudgetConfig as _CascadingBudgetConfig

        self.config = config or _CascadingBudgetConfig()
        self._proposal = BudgetController(self.config.proposal)
        self._filter_state = FilterBudgetState()

    def start_frame(self) -> None:
        """在新一帧开始时调用，复用 proposal 的计时逻辑。"""
        self._proposal.start_frame()

    def elapsed_ms(self) -> float:
        return self._proposal.elapsed_ms()

    def remaining_budget_ms(self) -> float:
        """Proposal 阶段后的剩余预算。"""
        return self._proposal.remaining_budget_ms()

    def filter_budget_ms(self) -> float:
        """Filter 阶段可用预算上限。"""
        return min(
            self.config.filter_hard_limit_ms,
            self.remaining_budget_ms() * self.config.filter_budget_ratio,
        )

    def regulate(self, heatmap: np.ndarray) -> tuple[float, int, str]:
        """委托给内部 BudgetController。"""
        return self._proposal.regulate(heatmap)

    def record_cc_count(self, count: int) -> None:
        self._proposal.record_cc_count(count)

    def schedule_filter(
        self, proposals: list[Any]
    ) -> tuple[list[Any], list[Any], str]:
        """根据剩余预算决定哪些 proposal 送 Filter。

        Args:
            proposals: 按 priority 已排序的 proposal 列表

        Returns:
            (to_filter, skip, mode)
            to_filter — 送 Filter 推理的 proposal
            skip — 因预算不足跳过的 proposal
            mode — "full" | "partial" | "skip_all" | "emergency"
        """
        if not self.config.enabled:
            return (proposals, [], "full")

        budget_ms = self.filter_budget_ms()
        hard_limit = self.config.filter_hard_limit_ms
        emergency_limit = hard_limit * self.config.emergency_filter_ratio

        # Emergency: 剩余预算极少
        if budget_ms < emergency_limit:
            self._filter_state.emergency_skip_count += 1
            for p in proposals:
                if p.filter_result is None:
                    p.filter_result = self._build_skip_result("emergency")
            return ([], proposals, "emergency")

        # 计算可处理的最大 patch 数
        max_filter = max(1, int(
            budget_ms / max(0.1, self._filter_state.estimated_cost_per_patch_ms)
        ))
        max_filter = max(self.config.filter_min_patches, max_filter)

        if max_filter >= len(proposals):
            return (proposals, [], "full")

        if max_filter >= self.config.filter_min_patches:
            self._filter_state.skip_count += len(proposals) - max_filter
            to_filter = proposals[:max_filter]
            skip = proposals[max_filter:]
            for p in skip:
                if p.filter_result is None:
                    p.filter_result = self._build_skip_result("partial_budget")
            return (to_filter, skip, "partial")

        # 一个都处理不了
        self._filter_state.skip_count += len(proposals)
        for p in proposals:
            if p.filter_result is None:
                p.filter_result = self._build_skip_result("skip_all")
        return ([], proposals, "skip_all")

    def record_filter_cost(self, num_patches: int, total_ms: float) -> None:
        """每帧结束后反馈实际 Filter 耗时，更新 EMA 估计。"""
        if num_patches == 0:
            return
        cost = total_ms / num_patches
        alpha = self.config.filter_cost_ema_alpha
        self._filter_state.estimated_cost_per_patch_ms = (
            alpha * self._filter_state.estimated_cost_per_patch_ms
            + (1.0 - alpha) * cost
        )
        self._filter_state.recent_costs_ms.append(total_ms)
        if len(self._filter_state.recent_costs_ms) > 100:
            self._filter_state.recent_costs_ms.pop(0)

    @staticmethod
    def _build_skip_result(reason: str) -> "FilterResult":
        from .._protocol import FilterResult

        return FilterResult(
            is_real_defect=True,  # 保守：不抑制
            confidence=0.0,
            real_defect_score=0.0,
            false_alarm_score=0.0,
            class_id=1,
            diagnostics={"filter_mode": "budget_skip", "reason": reason},
        )
