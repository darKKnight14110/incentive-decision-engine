"""Typed cross-plane contracts used in manifests and portfolio artifacts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSelectionResult:
    selected_model: str
    validation_metrics: dict[str, float]
    stability: dict[str, float]
    threshold: float | None
    rejection_reason: str | None


@dataclass(frozen=True)
class EstimatorRecoverySummary:
    dgp: str
    estimator: str
    bias: float
    rmse: float
    coverage: float
    mean_interval_width: float


@dataclass(frozen=True)
class ModelRunManifest:
    config_hash: str
    data_hash: str
    split_hash: str
    seeds: list[int]
    dependencies: dict[str, str]
    git_revision: str | None
    runtime_seconds: float
    peak_memory_bytes: int
