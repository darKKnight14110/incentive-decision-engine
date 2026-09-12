"""Multiple-choice knapsack allocation with hard operational constraints."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix, vstack as sparse_vstack

@dataclass(frozen=True)
class AllocationResult:
    assignments: pd.DataFrame
    expected_value: float
    expected_cost: float
    utilization: float
    marginal_budget_value: float | None
    violations: tuple[str, ...]
    rounding_error: float = 0.0
    binding_constraints: tuple[str, ...] = ()

def optimize_allocation(candidates: pd.DataFrame, budget: float, maximum_contact_volume: int | None = None, capacity: dict[str, float] | None = None, minimum_roi: float | None = None, segment_limits: dict[str, int] | None = None, return_shadow: bool = True) -> AllocationResult:
    required={"user_id","action","expected_value","expected_cost"}; missing=required-set(candidates.columns)
    if missing: raise ValueError(f"candidate contract missing {sorted(missing)}")
    if budget < 0: raise ValueError("budget must be non-negative")
    frame=candidates.reset_index(drop=True).copy(); n=len(frame); values=frame.expected_value.to_numpy(float); costs=frame.expected_cost.to_numpy(float)
    if not np.isfinite(values).all() or not np.isfinite(costs).all():
        raise ValueError("expected_value and expected_cost must be finite")
    if (costs < 0).any():
        raise ValueError("expected_cost cannot be negative")
    if "contact_allowed" in frame:
        frame = frame[(frame.contact_allowed.astype(bool)) | (frame.action == "no_offer")].reset_index(drop=True)
        n, values, costs = len(frame), frame.expected_value.to_numpy(float), frame.expected_cost.to_numpy(float)
    integrality=np.ones(n); bounds=Bounds(np.zeros(n), np.ones(n)); rows=[]; lows=[]; highs=[]
    rows.append(costs); lows.append(-np.inf); highs.append(budget)
    for _, idx in frame.groupby("user_id").groups.items():
        row=np.zeros(n); row[list(idx)]=1; rows.append(row); lows.append(-np.inf); highs.append(1)
    if maximum_contact_volume is not None:
        rows.append((frame.action != "no_offer").astype(float).to_numpy()); lows.append(-np.inf); highs.append(maximum_contact_volume)
    if segment_limits is not None and "segment" in frame:
        for segment, limit in segment_limits.items():
            rows.append((frame.segment == segment).astype(float).to_numpy()); lows.append(-np.inf); highs.append(limit)
    if capacity is not None and "city_hour" in frame:
        for key, limit in capacity.items():
            row=np.where(frame.city_hour == key, frame.get("expected_incremental_orders", pd.Series(0,index=frame.index)), 0).astype(float); rows.append(row); lows.append(-np.inf); highs.append(limit)
    if minimum_roi is not None:
        rows.append((frame.expected_value - minimum_roi*frame.expected_cost).to_numpy(float)); lows.append(0); highs.append(np.inf)
    # Keep the constraint matrix sparse. A dense user-by-action matrix becomes
    # needlessly expensive as the candidate population grows.
    constraint_matrix = sparse_vstack([csr_matrix(row) for row in rows], format="csr")
    result=milp(-values, integrality=integrality, bounds=bounds, constraints=LinearConstraint(constraint_matrix, np.asarray(lows), np.asarray(highs)), options={"time_limit": 60})
    if not result.success and result.x is None: raise RuntimeError(f"allocation solver failed: {result.message}")
    selected=frame[np.asarray(result.x) > .5].copy(); selected=selected.sort_values("user_id").reset_index(drop=True)
    cost=float(selected.expected_cost.sum()); value=float(selected.expected_value.sum())
    violations=[]
    if cost > budget + 1e-6: violations.append("budget")
    shadow=None
    if return_shadow and budget >= 0:
        nearby=optimize_allocation(frame, budget=max(0.0, budget-1.0), maximum_contact_volume=maximum_contact_volume, capacity=capacity, minimum_roi=minimum_roi, segment_limits=segment_limits, return_shadow=False)
        shadow=value-nearby.expected_value
    binding=[]
    if budget > 0 and abs(cost-budget) <= 1e-6:
        binding.append("budget")
    if maximum_contact_volume is not None and int((selected.action != "no_offer").sum()) >= maximum_contact_volume:
        binding.append("contact_volume")
    if segment_limits is not None and "segment" in frame:
        for segment, limit in segment_limits.items():
            if int((selected.segment == segment).sum()) >= limit:
                binding.append(f"segment:{segment}")
    if capacity is not None and "city_hour" in frame:
        for key, limit in capacity.items():
            usage = float(selected.loc[selected.city_hour == key, "expected_incremental_orders"].sum()) if "expected_incremental_orders" in selected else 0.0
            if usage >= float(limit) - 1e-6:
                binding.append(f"capacity:{key}")
    return AllocationResult(selected, value, cost, cost/budget if budget else 0.0, shadow, tuple(violations), 0.0, tuple(binding))
