"""Coordinate segmentation, pacing, scoring, optimization, and publishing."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.policy.pacer import BudgetPacer, BudgetPacerConfig, BudgetSnapshot
from src.policy.optimize import AllocationResult
from src.policy.solver import AllocationSolver, get_solver


@dataclass(frozen=True)
class TargetingRunConfig:
    run_id: str
    cycle: int
    total_cycles: int
    configured_budget: float
    realized_spend: float = 0.0
    predicted_liability: float = 0.0
    safety_buffer: float = 0.05
    solver_name: str = "highs"
    maximum_contact_volume: int | None = None
    capacity: dict[str, float] | None = None
    minimum_roi: float | None = None

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id must be non-empty")
        if self.cycle < 1 or self.total_cycles < 1 or self.cycle > self.total_cycles:
            raise ValueError("cycle must be within the configured horizon")
        if self.configured_budget < 0:
            raise ValueError("configured_budget must be non-negative")
        if self.realized_spend < 0 or self.predicted_liability < 0:
            raise ValueError("spend and liability must be non-negative")
        if self.maximum_contact_volume is not None and self.maximum_contact_volume < 0:
            raise ValueError("maximum_contact_volume must be non-negative")


@dataclass(frozen=True)
class TargetingRunResult:
    run_id: str
    budget: BudgetSnapshot
    allocation: AllocationResult
    solver_name: str


def run_targeting(
    candidates: pd.DataFrame,
    config: TargetingRunConfig,
    solver: AllocationSolver | None = None,
) -> TargetingRunResult:
    """Run one idempotent-style targeting decision from a candidate snapshot."""

    if "user_id" not in candidates or "action" not in candidates:
        raise ValueError("candidate snapshot must contain user_id and action")
    pacer = BudgetPacer(
        BudgetPacerConfig(
            total_budget=config.configured_budget,
            total_cycles=config.total_cycles,
            safety_buffer=config.safety_buffer,
        )
    )
    budget = pacer.reconcile(
        cycle=config.cycle,
        realized_spend=config.realized_spend,
        predicted_liability=config.predicted_liability,
    )
    backend = solver or get_solver(config.solver_name)
    allocation = backend.solve(
        candidates,
        budget=budget.recommended_budget,
        maximum_contact_volume=config.maximum_contact_volume,
        capacity=config.capacity,
        minimum_roi=config.minimum_roi,
        return_shadow=True,
    )
    return TargetingRunResult(config.run_id, budget, allocation, backend.name)
