"""Transparent heuristic baselines for optimizer sanity checks."""

from __future__ import annotations

import pandas as pd


def _feasible_add(selected: list[dict], candidate: dict, budget: float, maximum_contact_volume: int | None, capacity: dict[str, float] | None, segment_limits: dict[str, int] | None, minimum_roi: float | None) -> bool:
    if any(row["user_id"] == candidate["user_id"] for row in selected):
        return False
    if sum(float(row["expected_cost"]) for row in selected) + float(candidate["expected_cost"]) > budget + 1e-9:
        return False
    if maximum_contact_volume is not None and candidate["action"] != "no_offer":
        contacts = sum(row["action"] != "no_offer" for row in selected)
        if contacts + 1 > maximum_contact_volume:
            return False
    if minimum_roi is not None and float(candidate["expected_value"]) - minimum_roi * float(candidate["expected_cost"]) < -1e-9:
        return False
    if segment_limits is not None and "segment" in candidate:
        used = sum(row.get("segment") == candidate["segment"] for row in selected)
        if used + 1 > segment_limits.get(candidate["segment"], 10**9):
            return False
    if capacity is not None and "city_hour" in candidate:
        key = candidate["city_hour"]
        quantity = float(candidate.get("expected_incremental_orders", 0.0))
        used = sum(float(row.get("expected_incremental_orders", 0.0)) for row in selected if row.get("city_hour") == key)
        if used + quantity > float(capacity.get(key, float("inf"))) + 1e-9:
            return False
    return True


def greedy_allocation(candidates: pd.DataFrame, budget: float, **kwargs: object) -> pd.DataFrame:
    """Add feasible actions in descending value-per-cost order."""

    frame = candidates[candidates.expected_value > 0].copy()
    frame["_density"] = frame.expected_value / frame.expected_cost.replace(0, 1e-9)
    rows: list[dict] = []
    for candidate in frame.sort_values(["_density", "expected_value"], ascending=False).to_dict("records"):
        if _feasible_add(rows, candidate, budget, kwargs.get("maximum_contact_volume"), kwargs.get("capacity"), kwargs.get("segment_limits"), kwargs.get("minimum_roi")):
            rows.append(candidate)
    return pd.DataFrame(rows, columns=candidates.columns)


def lagrangian_allocation(candidates: pd.DataFrame, budget: float, penalty: float | None = None, **kwargs: object) -> pd.DataFrame:
    """Choose per-user actions by value minus a budget multiplier, then repair constraints."""

    multiplier = 0.0 if penalty is None else float(penalty)
    frame = candidates.copy()
    frame["_score"] = frame.expected_value - multiplier * frame.expected_cost
    rows: list[dict] = []
    for _, group in frame.sort_values("_score", ascending=False).groupby("user_id", sort=False):
        candidate = group.iloc[0].to_dict()
        if candidate["action"] != "no_offer" and candidate["_score"] <= 0:
            continue
        if _feasible_add(rows, candidate, budget, kwargs.get("maximum_contact_volume"), kwargs.get("capacity"), kwargs.get("segment_limits"), kwargs.get("minimum_roi")):
            rows.append(candidate)
    return pd.DataFrame(rows, columns=candidates.columns)
