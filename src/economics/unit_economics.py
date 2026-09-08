"""Transparent unit-economics calculations for offer allocation.

The functions in this module deliberately accept estimates as arguments. They
do not fit a model or infer causal effects; later policy code supplies those
estimates from randomized or otherwise valid causal analyses.
"""

from __future__ import annotations

from math import isfinite
from typing import Literal

CostAccountingMode = Literal["exposure", "redemption"]


def _finite(value: float, name: str) -> float:
    """Return a finite numeric input or raise a readable validation error."""
    numeric = float(value)
    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def expected_offer_cost(
    face_value: float,
    redemption_rate: float,
    cost_accounting_mode: CostAccountingMode,
) -> float:
    """Calculate expected offer cost per assigned customer.

    ``exposure`` charges the face value whenever an offer is shown. ``redemption``
    charges the expected redeemed value, which is the face value multiplied by
    the redemption probability.
    """
    face = _finite(face_value, "face_value")
    redemption = _finite(redemption_rate, "redemption_rate")
    if face < 0:
        raise ValueError("face_value must be non-negative")
    if not 0 <= redemption <= 1:
        raise ValueError("redemption_rate must be between 0 and 1")
    if cost_accounting_mode not in {"exposure", "redemption"}:
        raise ValueError("cost_accounting_mode must be 'exposure' or 'redemption'")
    return face if cost_accounting_mode == "exposure" else face * redemption


def incremental_value(
    predicted_incremental_conversion: float,
    expected_contribution_margin: float,
    face_value: float,
    redemption_rate: float,
    cost_accounting_mode: CostAccountingMode,
) -> float:
    """Return expected net incremental contribution margin per customer.

    The contract is ``incremental conversion × contribution margin per order −
    expected offer cost``. The conversion input is a counterfactual increment,
    not the treated conversion rate.
    """
    conversion_lift = _finite(
        predicted_incremental_conversion, "predicted_incremental_conversion"
    )
    margin = _finite(expected_contribution_margin, "expected_contribution_margin")
    return conversion_lift * margin - expected_offer_cost(
        face_value, redemption_rate, cost_accounting_mode
    )


def cost_per_incremental_order(
    expected_cost: float, predicted_incremental_conversion: float
) -> float | None:
    """Return offer cost per incremental order, or ``None`` if undefined."""
    cost = _finite(expected_cost, "expected_cost")
    increment = _finite(
        predicted_incremental_conversion, "predicted_incremental_conversion"
    )
    if increment <= 0:
        return None
    return cost / increment


def return_on_investment(net_value: float, expected_cost: float) -> float | None:
    """Return net incremental value divided by offer cost, or ``None`` at zero cost."""
    value = _finite(net_value, "net_value")
    cost = _finite(expected_cost, "expected_cost")
    if cost <= 0:
        return None
    return value / cost
