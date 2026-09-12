"""Convert causal response estimates into incremental INR value."""
from __future__ import annotations
import pandas as pd
from src.economics.unit_economics import expected_offer_cost

def action_value(incremental_conversion: float, expected_margin: float, face_value: float, redemption_rate: float, mode: str = "redemption") -> tuple[float, float]:
    cost = expected_offer_cost(face_value, redemption_rate, mode)
    return float(incremental_conversion * expected_margin - cost), float(cost)

def candidate_values(frame: pd.DataFrame, expected_margin: float, offer_costs: dict[str, tuple[float, float]], mode: str = "redemption") -> pd.DataFrame:
    result = frame.copy()
    values = result.apply(lambda row: action_value(row["incremental_conversion"], expected_margin, *offer_costs.get(row["action"], (0.0, 0.0)), mode), axis=1)
    result[["expected_value", "expected_cost"]] = pd.DataFrame(values.tolist(), index=result.index)
    return result
