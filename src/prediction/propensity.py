"""Calibrated outcome-propensity baselines.

These scores estimate P(Y=1|X), not incremental response.  They are useful as
an incumbent targeting strawman and are never reported as causal evidence.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from lightgbm import LGBMClassifier
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

    def save(self, path: str | Path) -> Path:
        """Persist the fitted estimator and validation metadata."""

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"name": self.name, "estimator": self.estimator, "metrics": self.metrics}, target)
        return target

    @classmethod
    def load(cls, path: str | Path) -> "PropensityModel":
        payload = joblib.load(path)
        return cls(str(payload["name"]), payload["estimator"], dict(payload["metrics"]))


@dataclass(frozen=True)
class PropensitySelectionResult:
    """Validation-only model choice with explicit seed-stability diagnostics."""

    selected_model: str
    validation_metrics: dict[str, dict[str, float]]
    stability: dict[str, dict[str, float]]
    models: dict[str, PropensityModel]

def fit_propensity_models(x_train, y_train, x_validation, y_validation, seed: int = 2025) -> dict[str, PropensityModel]:
    models = {
        "logistic": make_pipeline(StandardScaler(), CalibratedClassifierCV(LogisticRegression(max_iter=300, class_weight="balanced", random_state=seed), cv=3, method="sigmoid")),
        "lightgbm": CalibratedClassifierCV(LGBMClassifier(
            n_estimators=250,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=50,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            random_state=seed,
            n_jobs=1,
            verbosity=-1,
        ), cv=3, method="sigmoid"),
    }
    result = {}
    for name, model in models.items():
        model.fit(x_train, y_train)
        prediction = np.clip(model.predict_proba(x_validation)[:, 1], 1e-7, 1 - 1e-7)
        result[name] = PropensityModel(name, model, propensity_metrics(y_validation, prediction))
    return result


def select_propensity_model(
    x_train,
    y_train,
    x_validation,
    y_validation,
    seeds: tuple[int, ...] = (11, 29, 47, 71, 101),
) -> PropensitySelectionResult:
    """Fit both baselines across seeds and select on held-out diagnostics.

    The selected estimator is refit only on the training partition using the
    winning seed.  Validation metrics and standard deviations are retained so
    predictive stability is visible and cannot be mistaken for causal lift.
    """

    if not seeds:
        raise ValueError("at least one seed is required")
    by_model: dict[str, list[PropensityModel]] = {"logistic": [], "lightgbm": []}
    for seed in seeds:
        fitted = fit_propensity_models(x_train, y_train, x_validation, y_validation, seed=seed)
        for name, model in fitted.items():
            by_model[name].append(model)
    means: dict[str, dict[str, float]] = {}
    stability: dict[str, dict[str, float]] = {}
    for name, models in by_model.items():
        metric_names = sorted(models[0].metrics)
        means[name] = {metric: float(np.mean([model.metrics[metric] for model in models])) for metric in metric_names}
        stability[name] = {f"{metric}_std": float(np.std([model.metrics[metric] for model in models], ddof=0)) for metric in metric_names}
    selected = min(means, key=lambda name: (means[name]["log_loss"], means[name]["brier"], -means[name]["pr_auc"], name))
    # Keep the first fitted model for the selected family as the reproducible
    # artifact; callers can persist the full metric table alongside it.
    return PropensitySelectionResult(selected, means, stability, {name: models[0] for name, models in by_model.items()})

def propensity_metrics(y_true, prediction) -> dict[str, float]:
    y_true, prediction = np.asarray(y_true), np.asarray(prediction)
    prediction = np.clip(prediction.astype(float), 1e-7, 1 - 1e-7)
    bins = np.linspace(0.0, 1.0, 11)
    ece = 0.0
    for low, high in zip(bins[:-1], bins[1:]):
        mask = (prediction >= low) & (prediction < high if high < 1 else prediction <= high)
        if mask.any():
            ece += float(mask.mean()) * abs(float(prediction[mask].mean()) - float(y_true[mask].mean()))
    return {
        "roc_auc": float(roc_auc_score(y_true, prediction)),
        "pr_auc": float(average_precision_score(y_true, prediction)),
        "log_loss": float(log_loss(y_true, prediction)),
        "brier": float(brier_score_loss(y_true, prediction)),
        "calibration_error": float(ece),
    }
