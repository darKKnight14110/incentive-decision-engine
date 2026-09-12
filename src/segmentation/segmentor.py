"""Leakage-safe segmentation for the targeting architecture.

Uber's public Tarot description calls segmentation a platform that produces an
eligible superset for the optimizer. This module implements that boundary in a
small, reproducible form. Rule segments are the default because they are
stable and explainable; the optional cluster segmentor is for discovery and
must be fit on pre-treatment training data only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


POST_TREATMENT_COLUMNS = {
    "treatment",
    "assignment",
    "exposure",
    "exposure_ts",
    "redemption",
    "redemption_ts",
    "conversion",
    "visit",
    "order_ts",
    "cancellation",
    "refund",
    "realized_margin",
}


def validate_segment_features(frame: pd.DataFrame, feature_columns: list[str]) -> None:
    """Reject missing, null, or post-treatment inputs before fitting."""

    missing = set(feature_columns) - set(frame.columns)
    if missing:
        raise ValueError(f"missing segmentation features: {sorted(missing)}")
    forbidden = {
        column
        for column in feature_columns
        if column.lower() in POST_TREATMENT_COLUMNS
        or any(token in column.lower() for token in ("exposure", "redemption", "conversion", "refund", "cancel"))
    }
    if forbidden:
        raise ValueError(f"post-treatment columns cannot define segments: {sorted(forbidden)}")
    if frame[feature_columns].isnull().any().any():
        raise ValueError("segmentation features cannot contain nulls")


@dataclass(frozen=True)
class SegmentProfile:
    """Versioned segment metadata used in reports and allocation constraints."""

    segment_id: str
    segment_name: str
    size: int
    share: float
    feature_means: dict[str, float]


class RuleBasedSegmentor:
    """Stable lifecycle segmentor for the eligible-user superset."""

    version = "rules-v1"

    def fit(self, frame: pd.DataFrame) -> "RuleBasedSegmentor":
        validate_segment_features(frame, ["engagement_score"])
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        validate_segment_features(frame, ["engagement_score"])
        result = frame.copy()
        score = result["engagement_score"].astype(float)
        result["segment_id"] = np.select(
            [score >= 0.55, score >= 0.25],
            ["active", "lapsing"],
            default="dormant",
        )
        result["segment_name"] = result["segment_id"]
        result["segment_version"] = self.version
        result["segment_score"] = score
        return result

    def fit_transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        return self.fit(frame).transform(frame)

    def profiles(self, frame: pd.DataFrame) -> list[SegmentProfile]:
        segmented = self.transform(frame)
        total = len(segmented)
        return [
            SegmentProfile(
                segment_id=str(segment_id),
                segment_name=str(segment_id),
                size=int(group.shape[0]),
                share=float(group.shape[0] / total) if total else 0.0,
                feature_means={"engagement_score": float(group.engagement_score.mean())},
            )
            for segment_id, group in segmented.groupby("segment_id", sort=True)
        ]


class ClusterSegmentor:
    """Optional train-only K-means segmentor for exploratory customer archetypes."""

    def __init__(self, n_clusters: int = 4, seed: int = 2025) -> None:
        if n_clusters < 2:
            raise ValueError("n_clusters must be at least 2")
        self.n_clusters = n_clusters
        self.seed = seed
        self.feature_columns: list[str] | None = None
        self.scaler: StandardScaler | None = None
        self.model: KMeans | None = None
        self.version = f"kmeans-v1-k{n_clusters}-s{seed}"

    def fit(self, frame: pd.DataFrame, feature_columns: list[str]) -> "ClusterSegmentor":
        validate_segment_features(frame, feature_columns)
        self.feature_columns = list(feature_columns)
        self.scaler = StandardScaler().fit(frame[self.feature_columns].astype(float))
        self.model = KMeans(n_clusters=self.n_clusters, n_init=20, random_state=self.seed)
        self.model.fit(self.scaler.transform(frame[self.feature_columns].astype(float)))
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if self.model is None or self.scaler is None or self.feature_columns is None:
            raise RuntimeError("fit must be called before transform")
        validate_segment_features(frame, self.feature_columns)
        result = frame.copy()
        scaled = self.scaler.transform(result[self.feature_columns].astype(float))
        labels = self.model.predict(scaled)
        distances = self.model.transform(scaled)
        result["segment_id"] = np.array([f"cluster_{label}" for label in labels], dtype=object)
        result["segment_name"] = result["segment_id"]
        result["segment_version"] = self.version
        result["segment_score"] = -distances.min(axis=1)
        return result

    def profiles(self, frame: pd.DataFrame) -> list[SegmentProfile]:
        segmented = self.transform(frame)
        total = len(segmented)
        return [
            SegmentProfile(
                segment_id=str(segment_id),
                segment_name=str(segment_id),
                size=int(group.shape[0]),
                share=float(group.shape[0] / total) if total else 0.0,
                feature_means={
                    column: float(group[column].mean()) for column in self.feature_columns or []
                },
            )
            for segment_id, group in segmented.groupby("segment_id", sort=True)
        ]
