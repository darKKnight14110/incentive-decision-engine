"""Small deterministic optimizer benchmark used by the DS acceptance gate."""

from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path

import pandas as pd

from src.policy.solver import CpSatSolver, HiGHSSolver
from src.policy.heuristics import exhaustive_allocation, greedy_allocation, lagrangian_allocation


def fixture(n_users: int = 80) -> pd.DataFrame:
    rows = []
    for user in range(n_users):
        rows.extend([
            {"user_id": f"u{user}", "action": "no_offer", "expected_value": 0.0, "expected_cost": 0.0, "segment": "base", "city_hour": f"c{user % 4}_12", "expected_incremental_orders": 0.0},
            {"user_id": f"u{user}", "action": "small_offer", "expected_value": 8.0 + user % 7, "expected_cost": 5.0, "segment": "base", "city_hour": f"c{user % 4}_12", "expected_incremental_orders": 1.0},
            {"user_id": f"u{user}", "action": "large_offer", "expected_value": 11.0 + user % 11, "expected_cost": 9.0, "segment": "base", "city_hour": f"c{user % 4}_12", "expected_incremental_orders": 1.5},
        ])
    return pd.DataFrame(rows)


def run(output_path: str | Path = "reports/optimizer_benchmark.json") -> dict[str, object]:
    candidates = fixture()
    capacity = {f"c{i}_12": 18.0 for i in range(4)}
    output: dict[str, object] = {"users": int(candidates.user_id.nunique()), "backends": {}}
    for backend in (HiGHSSolver(), CpSatSolver()):
        tracemalloc.start(); started = time.perf_counter()
        result = backend.solve(candidates, budget=320.0, maximum_contact_volume=40, capacity=capacity, return_shadow=False)
        _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
        output["backends"][backend.name] = {
            "expected_value": result.expected_value,
            "expected_cost": result.expected_cost,
            "assignments": len(result.assignments),
            "runtime_seconds": time.perf_counter() - started,
            "peak_memory_bytes": peak,
            "rounding_error": result.rounding_error,
        }
    highs = output["backends"]["highs"]["expected_value"]
    cpsat = output["backends"]["cp-sat"]["expected_value"]
    greedy = greedy_allocation(candidates, 320.0, maximum_contact_volume=40, capacity=capacity)
    lagrangian = lagrangian_allocation(candidates, 320.0, penalty=0.5, maximum_contact_volume=40, capacity=capacity)
    output["heuristics"] = {
        "greedy_expected_value": float(greedy.expected_value.sum()) if not greedy.empty else 0.0,
        "lagrangian_expected_value": float(lagrangian.expected_value.sum()) if not lagrangian.empty else 0.0,
        "greedy_gap_vs_highs": float(highs - (greedy.expected_value.sum() if not greedy.empty else 0.0)),
        "lagrangian_gap_vs_highs": float(highs - (lagrangian.expected_value.sum() if not lagrangian.empty else 0.0)),
    }
    # Exhaustive enumeration is intentionally limited to a five-user fixture,
    # providing a solver correctness oracle without pretending it scales.
    tiny = fixture(5)
    tiny_capacity = {f"c{i}_12": 2.5 for i in range(4)}
    exhaustive = exhaustive_allocation(
        tiny,
        20.0,
        maximum_contact_volume=3,
        capacity=tiny_capacity,
    )
    tiny_highs = HiGHSSolver().solve(
        tiny,
        20.0,
        maximum_contact_volume=3,
        capacity=tiny_capacity,
        return_shadow=False,
    )
    output["exhaustive_oracle"] = {
        "users": 5,
        "expected_value": float(exhaustive.expected_value.sum()) if not exhaustive.empty else 0.0,
        "highs_expected_value": tiny_highs.expected_value,
        "objective_difference": abs((float(exhaustive.expected_value.sum()) if not exhaustive.empty else 0.0) - tiny_highs.expected_value),
    }
    output["objective_difference"] = abs(highs - cpsat)
    output["parity_passed"] = (
        output["objective_difference"] <= 0.05
        and output["exhaustive_oracle"]["objective_difference"] <= 0.05
    )
    target = Path(output_path); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2), encoding="utf-8")
    if not output["parity_passed"]:
        raise RuntimeError(f"optimizer parity failed: {output['objective_difference']}")
    return output


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
