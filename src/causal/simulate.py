"""Small known-ground-truth DGPs for estimator validation."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class SimulatedCausalData:
    frame: pd.DataFrame
    true_ate: float
    true_tau: np.ndarray

def generate_causal_data(n: int = 2000, seed: int = 2025, effect: str = "heterogeneous", confounded: bool = False, poor_overlap: bool = False) -> SimulatedCausalData:
    if n < 20: raise ValueError("n must be at least 20")
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    if poor_overlap:
        propensity = np.where(x[:, 0] > 0, 0.92, 0.08)
    elif confounded:
        propensity = 1 / (1 + np.exp(-1.4 * x[:, 0]))
    else:
        propensity = np.full(n, 0.5)
    treatment = rng.binomial(1, propensity)
    tau = np.full(n, 0.15) if effect == "constant" else 0.1 + 0.15 * np.tanh(x[:, 1])
    baseline = 0.35 + 0.15 * np.tanh(x[:, 0])
    noise = rng.normal(scale=0.5, size=n)
    y = baseline + treatment * tau + (0.7 * x[:, 0] if confounded else 0) + noise
    return SimulatedCausalData(pd.DataFrame({"x0": x[:,0], "x1": x[:,1], "x2": x[:,2], "x3": x[:,3], "treatment": treatment, "outcome": y, "propensity": propensity}), float(tau.mean()), tau)
