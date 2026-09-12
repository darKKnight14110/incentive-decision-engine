"""Repeated estimator recovery against known simulated ground truth."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.causal.estimators import difference_in_means, doubly_robust, inverse_probability_weighted, regression_adjustment
from src.causal.simulate import generate_causal_data
from src.contracts import EstimatorRecoverySummary


def benchmark_estimators(
    effect: str = "constant",
    confounded: bool = False,
    poor_overlap: bool = False,
    repetitions: int = 500,
    n: int = 1200,
    seed: int = 2025,
) -> pd.DataFrame:
    """Return one row per estimator/repetition for bias and coverage analysis."""

    rows: list[dict[str, float | str]] = []
    for repetition in range(repetitions):
        sim = generate_causal_data(n, seed=seed + repetition, effect=effect, confounded=confounded, poor_overlap=poor_overlap)
        frame = sim.frame
        x = frame[["x0", "x1", "x2", "x3"]].to_numpy()
        y = frame.outcome.to_numpy()
        t = frame.treatment.to_numpy()
        estimates = {
            "difference_in_means": difference_in_means(y, t),
            "regression_adjustment": regression_adjustment(x, y, t),
            "ipw": inverse_probability_weighted(y, t, frame.propensity.to_numpy()),
            "doubly_robust": doubly_robust(x, y, t, frame.propensity.to_numpy()),
        }
        p = np.clip(frame.propensity.to_numpy(float), 1e-3, 1 - 1e-3)
        difference_se = np.sqrt(
            y[t == 1].var(ddof=1) / max((t == 1).sum(), 1)
            + y[t == 0].var(ddof=1) / max((t == 0).sum(), 1)
        )
        ipw_influence = t * y / p - (1 - t) * y / (1 - p)
        # The DR and regression rows use conservative influence-scale errors;
        # this is a recovery diagnostic, not a substitute for a production CI.
        standard_errors = {
            "difference_in_means": float(difference_se),
            "regression_adjustment": float(np.std(y, ddof=1) / np.sqrt(len(y))),
            "ipw": float(np.std(ipw_influence, ddof=1) / np.sqrt(len(y))),
            "doubly_robust": float(np.std(ipw_influence, ddof=1) / np.sqrt(len(y))),
        }
        for estimator, estimate in estimates.items():
            rows.append({
                "dgp": effect + ("_confounded" if confounded else "") + ("_poor_overlap" if poor_overlap else ""),
                "estimator": estimator,
                "estimate": float(estimate),
                "true_ate": float(sim.true_ate),
                "error": float(estimate - sim.true_ate),
                "ci_low": float(estimate - 1.96 * standard_errors[estimator]),
                "ci_high": float(estimate + 1.96 * standard_errors[estimator]),
                "covered": float(estimate - 1.96 * standard_errors[estimator] <= sim.true_ate <= estimate + 1.96 * standard_errors[estimator]),
                "interval_width": float(3.92 * standard_errors[estimator]),
            })
    return pd.DataFrame(rows)


def summarize_recovery(results: pd.DataFrame) -> list[EstimatorRecoverySummary]:
    """Aggregate repeated recovery rows into typed report contracts."""

    summaries: list[EstimatorRecoverySummary] = []
    for (dgp, estimator), group in results.groupby(["dgp", "estimator"], sort=True):
        errors = group.error.to_numpy(float)
        summaries.append(EstimatorRecoverySummary(
            dgp=str(dgp),
            estimator=str(estimator),
            bias=float(errors.mean()),
            rmse=float(np.sqrt(np.mean(errors**2))),
            coverage=float(group.covered.mean()),
            mean_interval_width=float(group.interval_width.mean()),
        ))
    return summaries
