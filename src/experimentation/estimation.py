"""Intent-to-treat estimates with transparent uncertainty contracts."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy import stats
from .diagnostics import sample_ratio_mismatch
from collections.abc import Iterable

@dataclass(frozen=True)
class ExperimentEstimate:
    point: float
    standard_error: float
    ci_low: float
    ci_high: float
    treated_n: int
    control_n: int
    srm_p: float
    outcome: str

def estimate_itt(frame: pd.DataFrame, outcome: str, treatment_column: str = "treatment", expected_probability: float = 0.85, alpha: float = 0.001, confidence_level: float = 0.95, fail_on_srm: bool = True) -> ExperimentEstimate:
    srm = sample_ratio_mismatch(frame[treatment_column], expected_probability, alpha)
    if fail_on_srm and not srm.passed:
        raise ValueError(f"sample-ratio mismatch detected (p={srm.p_value:.4g})")
    treated = frame.loc[frame[treatment_column] == 1, outcome].astype(float)
    control = frame.loc[frame[treatment_column] == 0, outcome].astype(float)
    point = float(treated.mean() - control.mean())
    se = float(np.sqrt(treated.var(ddof=1) / len(treated) + control.var(ddof=1) / len(control)))
    critical = float(stats.norm.ppf((1 + confidence_level) / 2))
    return ExperimentEstimate(point, se, point - critical * se, point + critical * se, len(treated), len(control), srm.p_value, outcome)


def estimate_itt_stream(
    chunks: Iterable[pd.DataFrame],
    outcome: str,
    treatment_column: str = "treatment",
    expected_probability: float = 0.85,
    alpha: float = 0.001,
    confidence_level: float = 0.95,
    fail_on_srm: bool = True,
) -> ExperimentEstimate:
    """Estimate ITT from validated chunks without materializing the dataset."""

    treated_n = control_n = 0
    treated_sum = control_sum = 0.0
    treated_sq = control_sq = 0.0
    for chunk in chunks:
        if outcome not in chunk or treatment_column not in chunk:
            raise ValueError(f"stream chunk must contain {outcome!r} and {treatment_column!r}")
        treatment = chunk[treatment_column].to_numpy(dtype=np.int8)
        values = chunk[outcome].to_numpy(dtype=float)
        treated = values[treatment == 1]
        control = values[treatment == 0]
        treated_n += len(treated); control_n += len(control)
        treated_sum += float(treated.sum()); control_sum += float(control.sum())
        treated_sq += float(np.square(treated).sum()); control_sq += float(np.square(control).sum())
    if min(treated_n, control_n) < 2:
        raise ValueError("stream must contain at least two observations per arm")
    srm = sample_ratio_mismatch(np.r_[np.ones(treated_n, dtype=np.int8), np.zeros(control_n, dtype=np.int8)], expected_probability, alpha)
    if fail_on_srm and not srm.passed:
        raise ValueError(f"sample-ratio mismatch detected (p={srm.p_value:.4g})")
    treated_mean = treated_sum / treated_n
    control_mean = control_sum / control_n
    treated_var = max(0.0, (treated_sq - treated_n * treated_mean**2) / (treated_n - 1))
    control_var = max(0.0, (control_sq - control_n * control_mean**2) / (control_n - 1))
    point = treated_mean - control_mean
    se = float(np.sqrt(treated_var / treated_n + control_var / control_n))
    critical = float(stats.norm.ppf((1 + confidence_level) / 2))
    return ExperimentEstimate(point, se, point - critical * se, point + critical * se, treated_n, control_n, srm.p_value, outcome)

def bootstrap_difference(frame: pd.DataFrame, outcome: str, treatment_column: str = "treatment", repetitions: int = 500, seed: int = 2025) -> np.ndarray:
    rng = np.random.default_rng(seed)
    treated = frame.loc[frame[treatment_column] == 1, outcome].to_numpy(float)
    control = frame.loc[frame[treatment_column] == 0, outcome].to_numpy(float)
    return np.asarray([rng.choice(treated, len(treated), replace=True).mean() - rng.choice(control, len(control), replace=True).mean() for _ in range(repetitions)])
