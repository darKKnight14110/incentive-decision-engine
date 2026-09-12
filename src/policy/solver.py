"""Pluggable optimizer backends.

The project keeps SciPy/HiGHS as its offline default and exposes a stable
backend boundary so CP-SAT or another production solver can be introduced
without changing the opportunity contract. Uber's public architecture makes
the same solver-swapping boundary explicit.
"""

from __future__ import annotations

from typing import Protocol

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
    """Optional OR-Tools backend placeholder with an explicit dependency gate.

    The repository does not force-install OR-Tools for its offline build. A
    caller that selects this backend gets a clear installation message rather
    than silently falling back to a different solver.
    """

    name = "cp-sat"

    def solve(self, candidates: pd.DataFrame, budget: float, **kwargs: object) -> AllocationResult:
        try:
            import ortools  # noqa: F401
        except ImportError as error:
            raise RuntimeError(
                "CpSatSolver requires optional dependency 'ortools'; use HiGHSSolver for offline runs"
            ) from error
        raise NotImplementedError(
            "CP-SAT adapter is intentionally not bundled; map the same candidate contract to OR-Tools here"
        )


def get_solver(name: str = "highs") -> AllocationSolver:
    """Return a named backend without coupling orchestration to a solver."""

    normalized = name.lower().replace("_", "-")
    if normalized == "highs":
        return HiGHSSolver()
    if normalized in {"cp-sat", "cpsat"}:
        return CpSatSolver()
    raise ValueError(f"unknown allocation solver: {name}")

