"""Calibrated outcome-propensity baselines.

These scores estimate P(Y=1|X), not incremental response.  They are useful as
an incumbent targeting strawman and are never reported as causal evidence.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

@dataclass
class PropensityModel:
    name: str
    estimator: object
    metrics: dict[str, float]

    def predict_proba(self, x: pd.DataFrame | np.ndarray) -> np.ndarray:
        return np.asarray(self.estimator.predict_proba(x))[:, 1]

def fit_propensity_models(x_train, y_train, x_validation, y_validation, seed: int = 2025) -> dict[str, PropensityModel]:
    models = {
        "logistic": make_pipeline(StandardScaler(), CalibratedClassifierCV(LogisticRegression(max_iter=300, class_weight="balanced", random_state=seed), cv=3, method="sigmoid")),
        "gradient_boosting": CalibratedClassifierCV(HistGradientBoostingClassifier(max_iter=150, learning_rate=0.05, max_leaf_nodes=31, random_state=seed), cv=3, method="sigmoid"),
    }
    result = {}
    for name, model in models.items():
        model.fit(x_train, y_train)
        prediction = np.clip(model.predict_proba(x_validation)[:, 1], 1e-7, 1 - 1e-7)
        result[name] = PropensityModel(name, model, propensity_metrics(y_validation, prediction))
    return result

def propensity_metrics(y_true, prediction) -> dict[str, float]:
    y_true, prediction = np.asarray(y_true), np.asarray(prediction)
    return {"roc_auc": float(roc_auc_score(y_true, prediction)), "pr_auc": float(average_precision_score(y_true, prediction)), "log_loss": float(log_loss(y_true, prediction)), "brier": float(brier_score_loss(y_true, prediction))}
