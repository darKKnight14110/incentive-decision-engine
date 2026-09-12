"""Validation-only selection utilities for heterogeneous-effect policies."""

from __future__ import annotations

import numpy as np

from src.contracts import ModelSelectionResult
from src.causal.evaluation import policy_value


def select_uplift_model(
    validation_outcome,
    validation_treatment,
    validation_predictions: dict[str, np.ndarray],
    constant_predictions: np.ndarray,
    assignment_probability: float,
    target_rate: float = 0.20,
) -> ModelSelectionResult:
    """Choose a learner using validation policy value only.

    The final test set is intentionally absent from this interface. Ties or
    uncertain improvements resolve to the constant-effect baseline.
    """

    y = np.asarray(validation_outcome, float)
    t = np.asarray(validation_treatment, int)
    constant = np.asarray(constant_predictions, float)
    scores: dict[str, float] = {}
    thresholds: dict[str, float] = {}
    for name, prediction in {"constant-effect": constant, **validation_predictions}.items():
        prediction = np.asarray(prediction, float)
        threshold = float(np.quantile(prediction, 1 - target_rate))
        scores[name] = policy_value(y, t, (prediction >= threshold).astype(int), assignment_probability)
        thresholds[name] = threshold
    selected = max(scores, key=scores.get)
    baseline = scores["constant-effect"]
    improvement = scores[selected] - baseline
    rejection_reason = None
    if selected != "constant-effect" and improvement <= 0:
        selected = "constant-effect"
        rejection_reason = "validation policy value did not beat constant-effect baseline"
    if selected == "constant-effect" and rejection_reason is None:
        rejection_reason = "constant-effect baseline selected on validation policy value"
    return ModelSelectionResult(
        selected_model=selected,
        validation_metrics={f"policy_value:{name}": float(value) for name, value in scores.items()},
        stability={"candidate_count": float(len(scores)), "validation_improvement_vs_constant": float(improvement)},
        threshold=thresholds[selected],
        rejection_reason=rejection_reason,
    )
