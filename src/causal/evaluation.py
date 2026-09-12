"""Held-out uplift and randomized policy-value metrics."""
from __future__ import annotations
import numpy as np
import pandas as pd

from dataclasses import dataclass

@dataclass(frozen=True)
class CATEPredictions:
    user_id: np.ndarray
    fold: np.ndarray
    tau_hat: np.ndarray
    model_name: str

@dataclass(frozen=True)
class PolicyValueEstimate:
    policy: str
    budget: float
    point: float
    ci_low: float
    ci_high: float
    spend: float
    treatment_rate: float

def uplift_deciles(y, treatment, score, n_bins: int = 10) -> pd.DataFrame:
    frame = pd.DataFrame({"y": y, "treatment": treatment, "score": score}).sort_values("score", ascending=False).reset_index(drop=True)
    frame["decile"] = pd.qcut(np.arange(len(frame)), q=min(n_bins, len(frame)), labels=False, duplicates="drop") + 1
    rows=[]
    for decile, group in frame.groupby("decile", observed=True):
        t, c = group[group.treatment==1].y, group[group.treatment==0].y
        rows.append({"decile": int(decile), "n": len(group), "treated_rate": len(t)/len(group), "control_rate": len(c)/len(group), "uplift": (t.mean() if len(t) else 0)-(c.mean() if len(c) else 0)})
    return pd.DataFrame(rows)

def qini_curve(y, treatment, score):
    order = np.argsort(-np.asarray(score)); y, t = np.asarray(y)[order], np.asarray(treatment)[order]
    cum_t, cum_c = np.cumsum(t), np.cumsum(1-t); cum_y_t, cum_y_c = np.cumsum(y*t), np.cumsum(y*(1-t))
    return np.arange(1, len(y)+1), cum_y_t - cum_y_c * np.divide(cum_t, np.maximum(cum_c, 1))

def qini_auc(y, treatment, score) -> float:
    """Area under the cumulative Qini curve (higher is better)."""
    x, curve = qini_curve(y, treatment, score)
    return float(np.trapz(curve, x))

def auuc(y, treatment, score) -> float:
    """Area under the uplift curve, normalized by population size."""
    deciles = uplift_deciles(y, treatment, score, n_bins=20)
    return float(np.mean(deciles.uplift)) if len(deciles) else 0.0

def policy_value(y, treatment, policy_treat, assignment_probability: float | None = None) -> float:
    y, t, d = np.asarray(y, float), np.asarray(treatment, int), np.asarray(policy_treat, int)
    p = float(t.mean()) if assignment_probability is None else assignment_probability
    p = np.clip(p, 1e-4, 1-1e-4)
    contribution = d * (t*y/p - (1-t)*y/(1-p))
    return float(np.mean(contribution))

def bootstrap_policy_value(y, treatment, policy_treat, repetitions=500, seed=2025):
    rng=np.random.default_rng(seed); idx=np.arange(len(y)); values=[]
    for _ in range(repetitions):
        sample=rng.choice(idx, len(idx), replace=True); values.append(policy_value(np.asarray(y)[sample], np.asarray(treatment)[sample], np.asarray(policy_treat)[sample]))
    return np.asarray(values)

def summarize_policy_value(policy: str, budget: float, y, treatment, policy_treat, spend: float, repetitions: int = 500, seed: int = 2025) -> PolicyValueEstimate:
    draws = bootstrap_policy_value(y, treatment, policy_treat, repetitions, seed)
    return PolicyValueEstimate(policy, float(budget), float(draws.mean()), float(np.quantile(draws, .025)), float(np.quantile(draws, .975)), float(spend), float(np.mean(policy_treat)))
