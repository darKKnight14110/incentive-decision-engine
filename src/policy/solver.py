"""Pluggable optimizer backends.

The project keeps SciPy/HiGHS as its offline default and exposes a stable
backend boundary so CP-SAT or another production solver can be introduced
without changing the opportunity contract. Uber's public architecture makes
the same solver-swapping boundary explicit.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
import pandas as pd

from src.policy.optimize import AllocationResult, optimize_allocation


class AllocationSolver(Protocol):
    """Structural interface implemented by every optimizer backend."""

    name: str

    def solve(self, candidates: pd.DataFrame, budget: float, **kwargs: object) -> AllocationResult:
        ...


class HiGHSSolver:
    """Deterministic SciPy/HiGHS backend used by smoke and test runs."""

    name = "highs"

    def solve(self, candidates: pd.DataFrame, budget: float, **kwargs: object) -> AllocationResult:
        return optimize_allocation(candidates, budget=budget, **kwargs)


class CpSatSolver:
    """OR-Tools CP-SAT backend using the same multiple-choice contract as HiGHS.

    CP-SAT requires integer coefficients. Values and costs are represented in
    paise-equivalent units and capacities in configurable milli-units. The
    result reports the maximum coefficient rounding error for auditability.
    """

    name = "cp-sat"

    def solve(self, candidates: pd.DataFrame, budget: float, **kwargs: object) -> AllocationResult:
        try:
            from ortools.sat.python import cp_model
        except ImportError as error:
            raise RuntimeError(
                "CpSatSolver requires optional dependency 'ortools'; use HiGHSSolver for offline runs"
            ) from error
        return self._solve_once(candidates, budget, cp_model, compute_shadow=bool(kwargs.pop("return_shadow", True)), **kwargs)

    def _solve_once(
        self,
        candidates: pd.DataFrame,
        budget: float,
        cp_model: object,
        compute_shadow: bool = False,
        **kwargs: object,
    ) -> AllocationResult:
        required = {"user_id", "action", "expected_value", "expected_cost"}
        missing = required - set(candidates.columns)
        if missing:
            raise ValueError(f"candidate contract missing {sorted(missing)}")
        if budget < 0:
            raise ValueError("budget must be non-negative")
        frame = candidates.reset_index(drop=True).copy()
        if "contact_allowed" in frame:
            frame = frame[(frame.contact_allowed.astype(bool)) | (frame.action == "no_offer")].reset_index(drop=True)
        n = len(frame)
        if n == 0:
            return AllocationResult(frame, 0.0, 0.0, 0.0, None, (), 0.0, ())

        value_scale = 100
        cost_scale = 100
        capacity_scale = 1000
        values = frame.expected_value.astype(float).to_numpy()
        costs = frame.expected_cost.astype(float).to_numpy()
        if not np.isfinite(values).all() or not np.isfinite(costs).all():
            raise ValueError("expected_value and expected_cost must be finite")
        if (costs < 0).any():
            raise ValueError("expected_cost cannot be negative")
        value_int = np.rint(values * value_scale).astype(int)
        cost_int = np.rint(costs * cost_scale).astype(int)
        model = cp_model.CpModel()
        variables = [model.NewBoolVar(f"candidate_{i}") for i in range(n)]
        model.Add(sum(int(cost_int[i]) * variables[i] for i in range(n)) <= int(round(budget * cost_scale)))
        for _, indexes in frame.groupby("user_id").groups.items():
            model.Add(sum(variables[int(i)] for i in indexes) <= 1)
        maximum_contact_volume = kwargs.get("maximum_contact_volume")
        if maximum_contact_volume is not None:
            model.Add(sum(int(frame.action.iloc[i] != "no_offer") * variables[i] for i in range(n)) <= int(maximum_contact_volume))
        segment_limits = kwargs.get("segment_limits")
        if segment_limits is not None and "segment" in frame:
            for segment, limit in dict(segment_limits).items():
                model.Add(sum(int(frame.segment.iloc[i] == segment) * variables[i] for i in range(n)) <= int(limit))
        capacity = kwargs.get("capacity")
        capacity_int: dict[str, int] = {}
        if capacity is not None and "city_hour" in frame:
            for key, limit in dict(capacity).items():
                capacity_int[str(key)] = int(round(float(limit) * capacity_scale))
                quantities = np.rint(frame.get("expected_incremental_orders", pd.Series(0.0, index=frame.index)).astype(float).to_numpy() * capacity_scale).astype(int)
                model.Add(sum(int(quantities[i]) * int(frame.city_hour.iloc[i] == key) * variables[i] for i in range(n)) <= capacity_int[str(key)])
        minimum_roi = kwargs.get("minimum_roi")
        if minimum_roi is not None:
            roi_scale = 100
            coefficients = np.rint((values - float(minimum_roi) * costs) * roi_scale).astype(int)
            model.Add(sum(int(coefficients[i]) * variables[i] for i in range(n)) >= 0)
        model.Maximize(sum(int(value_int[i]) * variables[i] for i in range(n)))
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 2025
        solver.parameters.max_time_in_seconds = float(kwargs.get("time_limit", 60.0))
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError(f"allocation solver failed: {solver.StatusName(status)}")
        selected = frame[[bool(solver.Value(variable)) for variable in variables]].copy().sort_values("user_id").reset_index(drop=True)
        cost = float(selected.expected_cost.sum())
        value = float(selected.expected_value.sum())
        violations = ("budget",) if cost > budget + 1e-6 else ()
        shadow = None
        if compute_shadow and budget >= 1.0:
            nearby = self._solve_once(frame, max(0.0, budget - 1.0), cp_model, compute_shadow=False, **kwargs)
            shadow = value - nearby.expected_value
        rounding_error = float(np.max(np.abs(value_int / value_scale - values)) + np.max(np.abs(cost_int / cost_scale - costs)))
        binding = []
        if budget > 0 and abs(cost - budget) <= 1e-6:
            binding.append("budget")
        if maximum_contact_volume is not None and int((selected.action != "no_offer").sum()) >= int(maximum_contact_volume):
            binding.append("contact_volume")
        return AllocationResult(selected, value, cost, cost / budget if budget else 0.0, shadow, violations, rounding_error, tuple(binding))


def get_solver(name: str = "highs") -> AllocationSolver:
    """Return a named backend without coupling orchestration to a solver."""

    normalized = name.lower().replace("_", "-")
    if normalized == "highs":
        return HiGHSSolver()
    if normalized in {"cp-sat", "cpsat"}:
        return CpSatSolver()
    raise ValueError(f"unknown allocation solver: {name}")
