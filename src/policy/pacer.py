"""Budget-pacing control loop for weekly targeting runs.

The public Uber Tarot architecture separates deterministic budget pacing from
probabilistic ML scoring. This implementation reconciles configured budget,
realized spend, and outstanding predicted liability before every optimizer
call. It is deliberately state-light so it can be backed by a database or
service in a production deployment.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetPacerConfig:
    """Configuration for a finite-horizon budget control loop."""

    total_budget: float
    total_cycles: int
    safety_buffer: float = 0.05
    max_cycle_budget: float | None = None

    def __post_init__(self) -> None:
        if self.total_budget < 0:
            raise ValueError("total_budget must be non-negative")
        if self.total_cycles < 1:
            raise ValueError("total_cycles must be at least one")
        if not 0 <= self.safety_buffer < 1:
            raise ValueError("safety_buffer must be in [0, 1)")
        if self.max_cycle_budget is not None and self.max_cycle_budget < 0:
            raise ValueError("max_cycle_budget must be non-negative")


@dataclass(frozen=True)
class BudgetSnapshot:
    """Auditable pacing decision emitted before allocation."""

    cycle: int
    configured_budget: float
    realized_spend: float
    predicted_liability: float
    remaining_budget: float
    recommended_budget: float
    utilization: float
    status: str


class BudgetPacer:
    """Reconcile spend velocity without allowing the optimizer to overspend."""

    def __init__(self, config: BudgetPacerConfig) -> None:
        self.config = config

    def reconcile(
        self,
        cycle: int,
        realized_spend: float,
        predicted_liability: float = 0.0,
    ) -> BudgetSnapshot:
        if not 1 <= cycle <= self.config.total_cycles:
            raise ValueError("cycle must be within the configured horizon")
        if realized_spend < 0 or predicted_liability < 0:
            raise ValueError("spend and liability must be non-negative")

        remaining = max(
            0.0,
            self.config.total_budget - realized_spend - predicted_liability,
        )
        cycles_left = max(1, self.config.total_cycles - cycle + 1)
        # Keep a small reserve so forecast error cannot consume the full budget.
        target = remaining / cycles_left * (1.0 - self.config.safety_buffer)
        if self.config.max_cycle_budget is not None:
            target = min(target, self.config.max_cycle_budget)
        utilization = (
            (realized_spend + predicted_liability) / self.config.total_budget
            if self.config.total_budget
            else 0.0
        )
        status = "pause" if remaining <= 0 else "run"
        return BudgetSnapshot(
            cycle=cycle,
            configured_budget=self.config.total_budget,
            realized_spend=float(realized_spend),
            predicted_liability=float(predicted_liability),
            remaining_budget=float(remaining),
            recommended_budget=float(max(0.0, target)),
            utilization=float(utilization),
            status=status,
        )

