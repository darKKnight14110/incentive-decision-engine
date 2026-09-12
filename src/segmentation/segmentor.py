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
from sklearn.metrics import adjusted_rand_score, silhouette_score
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


def cluster_stability_report(
    train_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
    feature_columns: list[str],
    cluster_counts: tuple[int, ...] = (2, 3, 4, 5),
    seeds: tuple[int, ...] = (11, 29, 47, 71, 101),
) -> pd.DataFrame:
    """Measure train-only K-means stability on a held-out validation snapshot.

    Scaling, centroids, and labels are fit independently on ``train_frame``.
    Validation rows are used only to compare silhouette quality and agreement
    across seeded fits.  The returned table is therefore safe to use as a
    diagnostic gate without leaking outcomes or treatment into segmentation.
    """

    if not cluster_counts or not seeds:
        raise ValueError("cluster_counts and seeds must be non-empty")
    validate_segment_features(train_frame, feature_columns)
    validate_segment_features(validation_frame, feature_columns)
    rows: list[dict[str, float | int | bool]] = []
    for n_clusters in cluster_counts:
        if n_clusters < 2:
            raise ValueError("cluster counts must be at least two")
        labels_by_seed: list[np.ndarray] = []
        silhouettes: list[float] = []
        for seed in seeds:
            segmentor = ClusterSegmentor(n_clusters=n_clusters, seed=seed).fit(train_frame, feature_columns)
            assert segmentor.scaler is not None and segmentor.model is not None
            scaled_validation = segmentor.scaler.transform(validation_frame[feature_columns].astype(float))
            labels = segmentor.model.predict(scaled_validation)
            labels_by_seed.append(labels)
            silhouettes.append(
                float(silhouette_score(scaled_validation, labels))
                if len(np.unique(labels)) > 1 and len(validation_frame) > n_clusters
                else float("nan")
            )
        pairwise = [
            adjusted_rand_score(left, right)
            for index, left in enumerate(labels_by_seed)
            for right in labels_by_seed[index + 1 :]
        ]
        rows.append(
            {
                "n_clusters": int(n_clusters),
                "ari_stability": float(np.mean(pairwise)) if pairwise else float("nan"),
                "ari_min": float(np.min(pairwise)) if pairwise else float("nan"),
                "silhouette_mean": float(np.nanmean(silhouettes)),
                "silhouette_min": float(np.nanmin(silhouettes)),
                "stability_gate_passed": bool(pairwise and np.mean(pairwise) >= 0.80),
            }
        )
    report = pd.DataFrame(rows)
    report["selected_diagnostic"] = False
    eligible = report[report.stability_gate_passed]
    if not eligible.empty:
        winner = eligible.sort_values(["silhouette_mean", "ari_stability", "n_clusters"], ascending=[False, False, True]).index[0]
        report.loc[winner, "selected_diagnostic"] = True
    return report
