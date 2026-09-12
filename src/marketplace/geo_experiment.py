"""Cluster-randomized validation design for marketplace interference."""
from __future__ import annotations
from dataclasses import dataclass
from math import ceil
from scipy.stats import norm

@dataclass(frozen=True)
class GeoExperimentDesign:
    clusters: int
    treatment_clusters: int
    control_clusters: int
    minimum_detectable_effect: float
    rationale: str

def geo_experiment_design(clusters: int, baseline_rate: float, cluster_size: int, intra_cluster_correlation: float = 0.02, alpha: float = .05, power: float = .8) -> GeoExperimentDesign:
    if clusters < 4 or cluster_size < 2: raise ValueError("at least four clusters and two users per cluster are required")
    treated=clusters//2; control=clusters-treated
    design_effect=1+(cluster_size-1)*intra_cluster_correlation
    se=(baseline_rate*(1-baseline_rate)*design_effect*(1/(treated*cluster_size)+1/(control*cluster_size)))**.5
    mde=float((norm.ppf(1-alpha/2)+norm.ppf(power))*se)
    return GeoExperimentDesign(clusters, treated, control, mde, "Cluster randomization protects against city-hour spillovers that violate user-level SUTVA.")
