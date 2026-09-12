"""Write an auditable, idempotent assignment artifact for downstream delivery."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


def publish_assignments(
    assignments: pd.DataFrame,
    output_path: str | Path,
    run_id: str,
    model_version: str,
    policy_version: str,
) -> pd.DataFrame:
    """Validate and persist one row per assigned user with audit metadata."""

    required = {"user_id", "action", "expected_value", "expected_cost"}
    missing = required - set(assignments.columns)
    if missing:
        raise ValueError(f"assignment contract missing {sorted(missing)}")
    if assignments.user_id.duplicated().any():
        raise ValueError("assignments must contain at most one row per user")
    result = assignments[["user_id", "action", "expected_value", "expected_cost"]].copy()
    result.insert(0, "run_id", run_id)
    result["model_version"] = model_version
    result["policy_version"] = policy_version
    result["assignment_id"] = result.apply(
        lambda row: hashlib.sha256(
            f"{run_id}|{row.user_id}|{row.action}".encode("utf-8")
        ).hexdigest()[:20],
        axis=1,
    )
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(target, index=False)
    return result

