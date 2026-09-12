"""Intent-to-treat estimates with transparent uncertainty contracts."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy import stats
from .diagnostics import sample_ratio_mismatch

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

def bootstrap_difference(frame: pd.DataFrame, outcome: str, treatment_column: str = "treatment", repetitions: int = 500, seed: int = 2025) -> np.ndarray:
    rng = np.random.default_rng(seed)
    treated = frame.loc[frame[treatment_column] == 1, outcome].to_numpy(float)
    control = frame.loc[frame[treatment_column] == 0, outcome].to_numpy(float)
    return np.asarray([rng.choice(treated, len(treated), replace=True).mean() - rng.choice(control, len(control), replace=True).mean() for _ in range(repetitions)])
