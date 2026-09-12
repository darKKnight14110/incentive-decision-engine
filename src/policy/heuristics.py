"""Transparent heuristic baselines for optimizer sanity checks."""

from __future__ import annotations

from itertools import product

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


def exhaustive_allocation(
    candidates: pd.DataFrame,
    budget: float,
    *,
    maximum_contact_volume: int | None = None,
    capacity: dict[str, float] | None = None,
    minimum_roi: float | None = None,
    segment_limits: dict[str, int] | None = None,
    max_combinations: int = 100_000,
) -> pd.DataFrame:
    """Enumerate the exact optimum for tiny fixtures.

    This is deliberately bounded and is a correctness oracle for the solver
    backends, not a production algorithm.  It includes the implicit option of
    selecting no action for each user and applies the same global constraints
    as :func:`src.policy.optimize.optimize_allocation`.
    """

    required = {"user_id", "action", "expected_value", "expected_cost"}
    missing = required - set(candidates.columns)
    if missing:
        raise ValueError(f"candidate contract missing {sorted(missing)}")
    if budget < 0:
        raise ValueError("budget must be non-negative")
    frame = candidates.reset_index(drop=True).copy()
    groups = [group for _, group in frame.groupby("user_id", sort=True)]
    combinations = 1
    for group in groups:
        combinations *= len(group) + 1
    if combinations > max_combinations:
        raise ValueError(f"fixture has {combinations} combinations; exhaustive oracle is bounded at {max_combinations}")

    best_rows: list[dict] = []
    best_value = 0.0
    for choices in product(*([range(-1, len(group)) for group in groups])):
        selected_parts = [groups[i].iloc[choice].to_dict() for i, choice in enumerate(choices) if choice >= 0]
        if not selected_parts:
            continue
        selected = pd.DataFrame(selected_parts)
        cost = float(selected["expected_cost"].sum())
        if cost > budget + 1e-9:
            continue
        if maximum_contact_volume is not None:
            contacts = int((selected["action"] != "no_offer").sum())
            if contacts > int(maximum_contact_volume):
                continue
        if segment_limits is not None and "segment" in selected:
            # Match the solver contract exactly: a segment limit is a limit on
            # selected candidate rows. (No-offer rows normally have no cost
            # and are omitted by the production publisher.)
            counts = selected["segment"].value_counts()
            if any(int(counts.get(segment, 0)) > int(limit) for segment, limit in segment_limits.items()):
                continue
        if capacity is not None and "city_hour" in selected:
            quantity = selected.get("expected_incremental_orders", pd.Series(0.0, index=selected.index)).astype(float)
            usage = quantity.groupby(selected["city_hour"]).sum()
            if any(float(usage.get(key, 0.0)) > float(limit) + 1e-9 for key, limit in capacity.items()):
                continue
        value = float(selected["expected_value"].sum())
        if minimum_roi is not None and value - float(minimum_roi) * cost < -1e-9:
            continue
        if value > best_value + 1e-9:
            best_value = value
            best_rows = selected_parts
    return pd.DataFrame(best_rows, columns=frame.columns)
