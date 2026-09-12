"""Bounded-memory evaluation helpers for the full Criteo archive."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


def policy_value_stream(
    chunks: Iterable[pd.DataFrame],
    learner,
    feature_columns: list[str],
    threshold: float,
    assignment_probability: float,
) -> dict[str, float]:
    """Evaluate a locked policy over every test row without materialization."""

    probability = float(np.clip(assignment_probability, 1e-4, 1 - 1e-4))
    total = 0.0
    rows = targeted = 0
    for chunk in chunks:
        scores = np.asarray(learner.predict(chunk[feature_columns].to_numpy()), dtype=float)
        treatment = chunk.treatment.to_numpy(dtype=np.int8)
        outcome = chunk.conversion.to_numpy(dtype=float)
        policy = scores >= threshold
        contribution = policy * (treatment * outcome / probability - (1 - treatment) * outcome / (1 - probability))
        total += float(contribution.sum())
        rows += len(chunk)
        targeted += int(policy.sum())
    return {
        "point": total / max(rows, 1),
        "rows": float(rows),
        "targeted": float(targeted),
        "treatment_rate": targeted / max(rows, 1),
        "threshold": float(threshold),
    }
