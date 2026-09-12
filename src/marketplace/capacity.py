"""Capacity-aware synthetic marketplace policy diagnostics."""
from __future__ import annotations
import pandas as pd

def capacity_summary(assignments: pd.DataFrame, capacity: pd.DataFrame) -> pd.DataFrame:
    required={"city_hour","expected_incremental_orders"}
    if not required <= set(assignments.columns): raise ValueError(f"missing {required-set(assignments.columns)}")
    demand=assignments.groupby("city_hour", as_index=False).expected_incremental_orders.sum().rename(columns={"expected_incremental_orders":"incremental_demand"})
    cap=capacity.rename(columns={"hour_ts":"city_hour","available_capacity_orders":"capacity"}) if "hour_ts" in capacity else capacity.copy()
    return demand.merge(cap[["city_hour","capacity"]], on="city_hour", how="left").assign(headroom=lambda x:x.capacity-x.incremental_demand, overloaded=lambda x:x.incremental_demand>x.capacity)

def apply_capacity_guardrail(candidates: pd.DataFrame, capacity: dict[str,float]) -> pd.DataFrame:
    result=candidates.copy()
    if "city_hour" not in result or "expected_incremental_orders" not in result: return result
    allowed=result.city_hour.map(capacity).fillna(float("inf"))
    return result[result.expected_incremental_orders <= allowed].copy()
