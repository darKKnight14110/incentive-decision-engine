"""Eligibility and customer segmentation contracts."""

from .segmentor import (
    ClusterSegmentor,
    RuleBasedSegmentor,
    SegmentProfile,
    cluster_stability_report,
    validate_segment_features,
)

__all__ = [
    "ClusterSegmentor",
    "RuleBasedSegmentor",
    "SegmentProfile",
    "cluster_stability_report",
    "validate_segment_features",
]
