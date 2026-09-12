"""Transparent S-, T-, and X-style heterogeneous-effect learners."""
from __future__ import annotations
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge

def _model(seed: int):
    return HistGradientBoostingRegressor(max_iter=120, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=30, random_state=seed)

class ConstantEffectLearner:
    def fit(self, x, treatment, outcome):
        t = np.asarray(treatment).astype(bool); y = np.asarray(outcome, float)
        self.effect_ = float(y[t].mean() - y[~t].mean()); return self
    def predict(self, x): return np.full(len(x), self.effect_)

class TLearner:
    def __init__(self, seed: int = 2025): self.seed = seed
    def fit(self, x, treatment, outcome):
        x, t, y = np.asarray(x), np.asarray(treatment).astype(bool), np.asarray(outcome, float)
        self.control_ = _model(self.seed).fit(x[~t], y[~t]); self.treated_ = _model(self.seed + 1).fit(x[t], y[t]); return self
    def predict(self, x):
        x = np.asarray(x); return self.treated_.predict(x) - self.control_.predict(x)

class XLearner:
    def __init__(self, seed: int = 2025): self.seed = seed
    def fit(self, x, treatment, outcome):
        x, t, y = np.asarray(x), np.asarray(treatment).astype(bool), np.asarray(outcome, float)
        self.control_ = _model(self.seed).fit(x[~t], y[~t]); self.treated_ = _model(self.seed+1).fit(x[t], y[t])
        d0 = self.treated_.predict(x[~t]) - y[~t]; d1 = y[t] - self.control_.predict(x[t])
        self.effect0_ = _model(self.seed+2).fit(x[~t], d0); self.effect1_ = _model(self.seed+3).fit(x[t], d1)
        self.propensity_ = float(t.mean()); return self
    def predict(self, x): return (1-self.propensity_) * self.effect0_.predict(x) + self.propensity_ * self.effect1_.predict(x)
