"""Fail-fast audit for evidence labels and implementation claims."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def audit_claims(root: str | Path = ".") -> list[str]:
    base = Path(root)
    readme = (base / "README.md").read_text(encoding="utf-8")
    errors: list[str] = []
    manifest_path = base / "reports" / "run_manifest.json"
    if not manifest_path.exists():
        errors.append("reports/run_manifest.json is missing; run make build first")
        return errors
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for field in ("config_hash", "dependencies", "git_revision", "runtime_seconds", "peak_memory_bytes", "seeds"):
        if field not in manifest:
            errors.append(f"run manifest missing {field}")
    mode = manifest.get("mode")
    if mode == "smoke":
        if "simulated" not in readme.lower() or "criteo-shaped" not in readme.lower():
            errors.append("smoke README result must be labelled simulated and Criteo-shaped")
        if "Measured experiment result" in readme:
            errors.append("smoke README cannot call the generated fixture measured")
    if "LightGBM" in readme and importlib.util.find_spec("lightgbm") is None:
        errors.append("README names LightGBM but the dependency is unavailable")
    claim = manifest.get("business_case_claim", {})
    if claim.get("claim_type") != "simulated_business_case":
        errors.append("business-case manifest must be labelled simulated_business_case")
    if "not realized business impact" not in readme.lower():
        errors.append("README must state that synthetic business value is not realized impact")
    registry_path = base / "reports" / "claim_registry.json"
    if not registry_path.exists():
        errors.append("reports/claim_registry.json is missing; rerun the pipeline")
    else:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        claims = {claim.get("id"): claim for claim in registry.get("claims", [])}
        if registry.get("schema_version") != "claims-v1":
            errors.append("claim registry schema version is unsupported")
        if "criteo_conversion_itt" not in claims or "synthetic_marketplace_policy" not in claims:
            errors.append("claim registry must contain Criteo ITT and synthetic policy claims")
        if mode == "smoke" and claims.get("criteo_conversion_itt", {}).get("label") != "simulated":
            errors.append("smoke Criteo claim must be labelled simulated in the registry")
        if claims.get("synthetic_marketplace_policy", {}).get("label") != "estimated illustration":
            errors.append("synthetic policy claim must be labelled estimated illustration")
    benchmark_path = base / "reports" / "optimizer_benchmark.json"
    if not benchmark_path.exists():
        errors.append("reports/optimizer_benchmark.json is missing; run make benchmark first")
    else:
        benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
        if not benchmark.get("parity_passed", False):
            errors.append("HiGHS/CP-SAT parity benchmark did not pass")
    return errors


def main() -> int:
    errors = audit_claims()
    if errors:
        for error in errors:
            print(f"CLAIM AUDIT FAILED: {error}")
        return 1
    print("claim audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
