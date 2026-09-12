"""Cross-fitted doubly robust learner."""
from __future__ import annotations
import numpy as np
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.model_selection import StratifiedKFold

class DRLearner:
    def __init__(self, n_splits: int = 5, seed: int = 2025): self.n_splits, self.seed = n_splits, seed
    def fit(self, x, treatment, outcome):
        x, t, y = np.asarray(x), np.asarray(treatment).astype(int), np.asarray(outcome, float)
        self.models_, self.propensities_ = [], []
        pseudo = np.zeros(len(y))
        folds = StratifiedKFold(self.n_splits, shuffle=True, random_state=self.seed)
        for train, holdout in folds.split(x, t):
            m0 = HistGradientBoostingRegressor(max_iter=120, learning_rate=.05, random_state=self.seed).fit(x[train][t[train]==0], y[train][t[train]==0])
            m1 = HistGradientBoostingRegressor(max_iter=120, learning_rate=.05, random_state=self.seed+1).fit(x[train][t[train]==1], y[train][t[train]==1])
            prop = HistGradientBoostingClassifier(max_iter=100, random_state=self.seed).fit(x[train], t[train])
            p = np.clip(prop.predict_proba(x[holdout])[:,1], .02, .98)
            m0h, m1h = m0.predict(x[holdout]), m1.predict(x[holdout]); th, yh = t[holdout], y[holdout]
            pseudo[holdout] = m1h - m0h + th*(yh-m1h)/p - (1-th)*(yh-m0h)/(1-p)
        self.effect_ = HistGradientBoostingRegressor(max_iter=150, learning_rate=.05, random_state=self.seed).fit(x, pseudo); return self
    def predict(self, x): return self.effect_.predict(np.asarray(x))
