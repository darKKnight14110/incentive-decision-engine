"""Unit-economics primitives used by the incentive decision engine."""

from .unit_economics import (
    CostAccountingMode,
    cost_per_incremental_order,
    expected_offer_cost,
    incremental_value,
    return_on_investment,
)

__all__ = [
    "CostAccountingMode",
    "cost_per_incremental_order",
    "expected_offer_cost",
    "incremental_value",
    "return_on_investment",
]
