"""Claim registry generated from a pipeline run manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_claim_registry(manifest: dict[str, Any]) -> dict[str, Any]:
    """Build a versioned registry of headline claims from ``manifest``."""

    mode = str(manifest.get("mode", "smoke"))
    estimate = dict(manifest.get("estimate", {}))
    claim = dict(manifest.get("business_case_claim", {}))
    criteo_status = "measured" if mode == "full" else "simulated"
    return {
        "schema_version": "claims-v1",
        "run_mode": mode,
        "run_manifest_revision": manifest.get("git_revision"),
        "claims": [
            {
                "id": "criteo_conversion_itt",
                "label": criteo_status,
                "source": "Criteo randomized advertising assignment",
                "outcome": "conversion",
                "point": estimate.get("point"),
                "ci_low": estimate.get("ci_low"),
                "ci_high": estimate.get("ci_high"),
                "rows": estimate.get("treated_n", 0) + estimate.get("control_n", 0),
                "caveat": "Smoke is a simulated Criteo-shaped fixture; full mode streams the validated archive.",
            },
            {
                "id": "synthetic_marketplace_policy",
                "label": "estimated illustration",
                "source": "Seeded synthetic marketplace economics and capacity",
                "point_inr_per_user": claim.get("incremental_value_vs_random_inr_per_eligible_user"),
                "ci_low_inr_per_user": claim.get("ci_low_inr_per_eligible_user"),
                "ci_high_inr_per_user": claim.get("ci_high_inr_per_eligible_user"),
                "budget_fraction": 0.50,
                "caveat": "Not realized business impact; replace assumptions with finance-approved economics and geo validation.",
            },
        ],
    }


def write_claim_registry(manifest: dict[str, Any], path: str | Path = "reports/claim_registry.json") -> Path:
    """Write the registry and return its path."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_claim_registry(manifest), indent=2), encoding="utf-8")
    return target
