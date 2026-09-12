"""Transparent S-, T-, and X-style heterogeneous-effect learners."""
from __future__ import annotations
from pathlib import Path
import joblib
import numpy as np
from lightgbm import LGBMRegressor
from sklearn.model_selection import StratifiedKFold

from src.causal.evaluation import CATEPredictions


class _Persistable:
    """Small shared persistence contract for fitted causal learners."""

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, target)
        return target

    @classmethod
    def load(cls, path: str | Path):
        return joblib.load(path)

def _model(seed: int, n_estimators: int = 220):
    return LGBMRegressor(
        n_estimators=n_estimators,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=30,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        random_state=seed,
        n_jobs=1,
        verbosity=-1,
    )

class ConstantEffectLearner(_Persistable):
    model_name = "constant-effect"

    def fit(self, x, treatment, outcome):
        t = np.asarray(treatment).astype(bool); y = np.asarray(outcome, float)
        self.effect_ = float(y[t].mean() - y[~t].mean()); return self
    def predict(self, x): return np.full(len(x), self.effect_)

class TLearner(_Persistable):
    def __init__(self, seed: int = 2025): self.seed = seed
    model_name = "t-learner"
    def fit(self, x, treatment, outcome):
        x, t, y = np.asarray(x), np.asarray(treatment).astype(bool), np.asarray(outcome, float)
        self.control_ = _model(self.seed).fit(x[~t], y[~t]); self.treated_ = _model(self.seed + 1).fit(x[t], y[t]); return self
    def predict(self, x):
        x = np.asarray(x); return self.treated_.predict(x) - self.control_.predict(x)

class XLearner(_Persistable):
    def __init__(self, seed: int = 2025): self.seed = seed
    model_name = "x-learner"
    def fit(self, x, treatment, outcome):
        x, t, y = np.asarray(x), np.asarray(treatment).astype(bool), np.asarray(outcome, float)
        self.control_ = _model(self.seed).fit(x[~t], y[~t]); self.treated_ = _model(self.seed+1).fit(x[t], y[t])
        d0 = self.treated_.predict(x[~t]) - y[~t]; d1 = y[t] - self.control_.predict(x[t])
        self.effect0_ = _model(self.seed+2).fit(x[~t], d0); self.effect1_ = _model(self.seed+3).fit(x[t], d1)
        self.propensity_ = float(t.mean()); return self
    def predict(self, x): return (1-self.propensity_) * self.effect0_.predict(x) + self.propensity_ * self.effect1_.predict(x)


def cross_fit_learner(
    learner_factory,
    x,
    treatment,
    outcome,
    user_id=None,
    n_splits: int = 5,
    seed: int = 2025,
) -> CATEPredictions:
    """Generate out-of-fold CATE predictions with fold-isolated fitting.

    The returned predictions are diagnostics for model selection and audit.
    A final learner must still be fit on the complete training partition before
    scoring a locked test partition.
    """

    x, treatment, outcome = np.asarray(x), np.asarray(treatment).astype(int), np.asarray(outcome, float)
    if len(x) != len(treatment) or len(x) != len(outcome):
        raise ValueError("x, treatment, and outcome must have equal length")
    if n_splits < 2:
        raise ValueError("n_splits must be at least two")
    ids = np.arange(len(x)) if user_id is None else np.asarray(user_id)
    if len(ids) != len(x):
        raise ValueError("user_id must have equal length to x")
    predictions = np.zeros(len(x), dtype=float)
    fold_ids = np.zeros(len(x), dtype=int)
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for fold, (train, holdout) in enumerate(splitter.split(x, treatment)):
        learner = learner_factory(seed + fold)
        learner.fit(x[train], treatment[train], outcome[train])
        predictions[holdout] = learner.predict(x[holdout])
        fold_ids[holdout] = fold
    name = getattr(learner_factory(seed), "model_name", learner_factory(seed).__class__.__name__)
    return CATEPredictions(ids, fold_ids, predictions, str(name))


def save_learner(learner, path: str | Path) -> Path:
    """Persist a fitted learner with its class and model version metadata."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model_name": getattr(learner, "model_name", learner.__class__.__name__), "learner": learner}, target)
    return target


def load_learner(path: str | Path):
    payload = joblib.load(path)
    return payload["learner"]
