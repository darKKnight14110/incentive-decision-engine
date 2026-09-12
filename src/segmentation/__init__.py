"""Eligibility and customer segmentation contracts."""

from .segmentor import (
    ClusterSegmentor,
    RuleBasedSegmentor,
    SegmentProfile,
    validate_segment_features,
)

__all__ = [
    "ClusterSegmentor",
    "RuleBasedSegmentor",
    "SegmentProfile",
    "validate_segment_features",
]

