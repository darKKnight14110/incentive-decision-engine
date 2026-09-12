"""Diagnostics that must run before interpreting randomized outcomes."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.stats import binomtest, chi2_contingency


@dataclass(frozen=True)
class SRMResult:
    observed_treated: int
    observed_control: int
    expected_treatment_probability: float
    p_value: float
    passed: bool


def sample_ratio_mismatch(treatment: pd.Series | np.ndarray, expected_probability: float = 0.85, alpha: float = 0.001) -> SRMResult:
    values = np.asarray(treatment, dtype=int)
    treated = int(values.sum())
    control = int(len(values) - treated)
    result = binomtest(treated, len(values), expected_probability)
    return SRMResult(treated, control, expected_probability, float(result.pvalue), bool(result.pvalue >= alpha))


def balance_report(frame: pd.DataFrame, features: list[str], treatment_column: str = "treatment") -> pd.DataFrame:
    rows = []
    treated = frame[frame[treatment_column] == 1]
    control = frame[frame[treatment_column] == 0]
    for feature in features:
        a, b = treated[feature].astype(float), control[feature].astype(float)
        pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
        rows.append({"feature": feature, "treated_mean": a.mean(), "control_mean": b.mean(), "std_mean_difference": (a.mean() - b.mean()) / pooled if pooled else 0.0})
    return pd.DataFrame(rows)


def aa_pvalues(outcome: np.ndarray, seed: int = 2025, repetitions: int = 500) -> np.ndarray:
    """A/A randomization p-values used to calibrate the inference code."""
    rng = np.random.default_rng(seed)
    outcome = np.asarray(outcome, dtype=float)
    pvalues = []
    for _ in range(repetitions):
        assignment = rng.binomial(1, 0.5, len(outcome))
        table = pd.crosstab(assignment, outcome > 0)
        pvalues.append(float(chi2_contingency(table, correction=False).pvalue) if table.shape == (2, 2) else 1.0)
    return np.asarray(pvalues)
