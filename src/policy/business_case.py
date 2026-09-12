"""Deterministic synthetic business case for the portfolio decision readout.

The Criteo data supports measured advertising incrementality, but it does not
contain INR economics or multi-action marketplace capacity.  This module keeps
those questions separate and creates a clearly labelled scenario in which the
allocator can be judged on a business objective.  The assumptions are
deliberately explicit, deterministic, and easy to replace with production
estimates.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import yaml

from src.policy.baselines import build_baseline_policy
from src.policy.optimize import AllocationResult, optimize_allocation
from src.orchestration.targeting import TargetingRunConfig, run_targeting
from src.segmentation.segmentor import RuleBasedSegmentor


@dataclass(frozen=True)
class BusinessCaseResult:
    """Outputs used by the report, dashboard, and resume-facing summary."""

    candidates: pd.DataFrame
    policy_results: pd.DataFrame
    sensitivity: pd.DataFrame
    canonical_claim: dict[str, float | str]
    optimizer_result: AllocationResult
    pacing_snapshot: object | None = None


def _load_assumptions(config_path: str = "configs/economics.yaml") -> dict[str, object]:
    """Load versioned scenario assumptions, falling back only for library use."""

    path = pd.io.common.stringify_path(config_path)
    try:
        with open(path, encoding="utf-8") as stream:
            loaded = yaml.safe_load(stream) or {}
        return dict(loaded.get("business_case", {}))
    except FileNotFoundError:
        return {
            "contribution_margin_inr": 520.0,
            "offers": {
                "no_offer": {"face_value_inr": 0.0, "redemption_rate": 0.0, "response_multiplier": 0.0},
                "small_offer": {"face_value_inr": 18.0, "redemption_rate": 0.35, "response_multiplier": 1.0},
                "large_offer": {"face_value_inr": 35.0, "redemption_rate": 0.55, "response_multiplier": 1.25},
            },
            "capacity_fraction_of_positive_demand": 0.28,
        }


def make_business_case_candidates(
    seed: int = 2025,
    n_users: int = 2_000,
    config_path: str = "configs/economics.yaml",
) -> pd.DataFrame:
    """Create user-action candidates with transparent INR and capacity inputs.

    The response surface contains useful heterogeneity: active customers have
    positive small-offer response, while a large offer is harmful for dormant
    customers once discount cost is included.  This makes ``no_offer`` a real
    option rather than a decorative row.
    """

    if n_users < 20:
        raise ValueError("n_users must be at least 20")
    rng = np.random.default_rng(seed)
    engagement = rng.beta(2.2, 3.0, n_users)
    city = rng.choice(["city_1", "city_2", "city_3", "city_4"], n_users, p=[.34, .28, .23, .15])
    preferred_hour = rng.integers(11, 22, n_users)
    users = pd.DataFrame(
        {
            "user_id": [f"u_{i:06d}" for i in range(n_users)],
            "engagement_score": engagement,
            "city_hour": [f"{c}_{h}" for c, h in zip(city, preferred_hour)],
        }
    )
    users = RuleBasedSegmentor().fit_transform(users)

    rows: list[dict[str, object]] = []
    # These are scenario assumptions, not estimates from Criteo.
    assumptions = _load_assumptions(config_path)
    margin_inr = float(assumptions.get("contribution_margin_inr", 520.0))
    configured_actions = assumptions.get("offers", {})
    actions = {
        action: (
            float(values.get("face_value_inr", 0.0)),
            float(values.get("redemption_rate", 0.0)),
            float(values.get("response_multiplier", 0.0)),
        )
        for action, values in configured_actions.items()
    }
    for user in users.itertuples(index=False):
        score = float(user.engagement_score)
        small_lift = 0.004 + 0.075 * score
        # Large discounts cannibalize dormant demand but work for active users.
        large_lift = -0.010 + 0.115 * score
        for action, (face, redemption, multiplier) in actions.items():
            lift = 0.0 if action == "no_offer" else (small_lift if action == "small_offer" else large_lift)
            lift *= multiplier
            cost = face * redemption
            rows.append(
                {
                    "user_id": user.user_id,
                    "action": action,
                    "incremental_conversion": lift,
                    "expected_margin": margin_inr,
                    "expected_cost": cost,
                    "expected_value": lift * margin_inr - cost,
                    # Scale conversion lift into treatment-driven demand so
                    # city-hour capacity is an active operational constraint.
                    "expected_incremental_orders": max(0.0, lift) * 20.0,
                    "city_hour": user.city_hour,
                    "segment": user.segment_id,
                    # Used by the propensity baseline as a predictive score.
                    "propensity_score": 0.02 + 0.20 * score,
                    "contact_allowed": True,
                }
            )
    return pd.DataFrame(rows)


def _user_bootstrap_difference(
    selected: pd.DataFrame,
    random_policy: pd.DataFrame,
    repetitions: int,
    seed: int,
) -> tuple[float, float, float]:
    """Bootstrap optimized-minus-random value over users, not action rows."""

    left = selected.groupby("user_id").expected_value.sum()
    right = random_policy.groupby("user_id").expected_value.sum()
    joined = pd.concat([left.rename("optimized"), right.rename("random")], axis=1).fillna(0.0)
    observed = float((joined.optimized - joined.random).mean())
    rng = np.random.default_rng(seed)
    values = np.empty(repetitions)
    for i in range(repetitions):
        sampled = joined.iloc[rng.integers(0, len(joined), len(joined))]
        values[i] = float((sampled.optimized - sampled.random).mean())
    return observed, float(np.quantile(values, .025)), float(np.quantile(values, .975))


def run_business_case(
    seed: int = 2025,
    n_users: int = 2_000,
    bootstrap_repetitions: int = 500,
    config_path: str = "configs/economics.yaml",
) -> BusinessCaseResult:
    """Evaluate all policies at matched budgets and return the canonical claim."""

    assumptions = _load_assumptions(config_path)
    candidates = make_business_case_candidates(seed, n_users, config_path)
    small_cost = float(candidates.loc[candidates.action == "small_offer", "expected_cost"].sum())
    capacity = {
        city_hour: max(
            0.5,
            float(group[group.action != "no_offer"].expected_incremental_orders.sum())
            * float(assumptions.get("capacity_fraction_of_positive_demand", 0.28)),
        )
        for city_hour, group in candidates.groupby("city_hour")
    }
    grid = (.10, .25, .50, .75, 1.00)
    rows: list[dict[str, float | str]] = []
    canonical_optimizer: AllocationResult | None = None
    canonical_random: pd.DataFrame | None = None
    canonical_pacing = None
    for fraction in grid:
        budget = small_cost * fraction
        optimized = optimize_allocation(
            candidates,
            budget=budget,
            maximum_contact_volume=int(n_users * .50),
            capacity=capacity,
            minimum_roi=0.0,
            return_shadow=True,
        )
        random_policy = build_baseline_policy(candidates, "random", budget, seed=seed)
        for name, policy in (("random", random_policy), ("optimized", optimized.assignments)):
            rows.append(
                {
                    "policy": name,
                    "budget_fraction": fraction,
                    "budget_inr": budget,
                    "expected_value_inr": float(policy.expected_value.sum()),
                    "expected_cost_inr": float(policy.expected_cost.sum()),
                    "treatment_rate": float(
                        policy.user_id.nunique() / n_users
                        if name == "optimized"
                        else (policy.action != "no_offer").mean()
                    ),
                    "capacity_aware": name == "optimized",
                    "marginal_budget_value_inr": (
                        float(optimized.marginal_budget_value or 0.0)
                        if name == "optimized"
                        else 0.0
                    ),
                }
            )
        if fraction == .50:
            canonical_optimizer = optimized
            canonical_random = random_policy
            # Exercise the same orchestration boundary used by a production
            # targeting run. A one-cycle run preserves the canonical budget
            # while still emitting an auditable pacing snapshot.
            targeting = run_targeting(
                candidates,
                TargetingRunConfig(
                    run_id=f"business-case-{seed}",
                    cycle=1,
                    total_cycles=1,
                    configured_budget=budget,
                    safety_buffer=0.0,
                    maximum_contact_volume=int(n_users * .50),
                    capacity=capacity,
                    minimum_roi=0.0,
                ),
            )
            canonical_optimizer = targeting.allocation
            canonical_pacing = targeting.budget

    if canonical_optimizer is None or canonical_random is None:
        raise RuntimeError("canonical budget was not evaluated")
    difference, ci_low, ci_high = _user_bootstrap_difference(
        canonical_optimizer.assignments,
        canonical_random,
        bootstrap_repetitions,
        seed + 1,
    )
    optimized_value = float(canonical_optimizer.expected_value)
    random_value = float(canonical_random.expected_value.sum())
    claim = {
        "claim_type": "simulated_business_case",
        "canonical_budget_fraction": str(assumptions.get("canonical_budget_fraction", 0.50)),
        "optimized_expected_value_inr": optimized_value,
        "random_expected_value_inr": random_value,
        "incremental_value_vs_random_inr_per_eligible_user": difference,
        "incremental_value_vs_random_inr_total": float(optimized_value - random_value),
        "relative_lift_vs_random_pct": float(
            100.0 * (optimized_value - random_value) / max(abs(random_value), 1e-9)
        ),
        "ci_low_inr_per_eligible_user": ci_low,
        "ci_high_inr_per_eligible_user": ci_high,
        "optimized_spend_inr": float(canonical_optimizer.expected_cost),
        "optimized_treatment_rate": float(canonical_optimizer.assignments.user_id.nunique() / n_users),
        "solver_backend": "highs",
        "pacer_recommended_budget_inr": float(canonical_pacing.recommended_budget) if canonical_pacing else float(small_cost * 0.50),
        "interpretation": (
            "Under the configured synthetic economics, the capacity-aware policy "
            "creates positive expected contribution margin versus random at the "
            "canonical 50% budget. This is an estimated illustration, not realized impact."
        ),
    }
    policy_results = pd.DataFrame(rows)
    sensitivity_rows: list[dict[str, float | str]] = []
    base_margin = float(assumptions.get("contribution_margin_inr", 520.0))
    for margin_multiplier in (0.75, 1.00, 1.25):
        for capacity_fraction in (0.20, 0.28, 0.40):
            scenario = candidates.copy()
            scenario["expected_value"] = (
                scenario.incremental_conversion * base_margin * margin_multiplier
                - scenario.expected_cost
            )
            scenario_capacity = {
                city_hour: max(
                    0.5,
                    float(group[group.action != "no_offer"].expected_incremental_orders.sum())
                    * capacity_fraction,
                )
                for city_hour, group in scenario.groupby("city_hour")
            }
            scenario_optimizer = optimize_allocation(
                scenario,
                budget=small_cost * 0.50,
                maximum_contact_volume=int(n_users * 0.50),
                capacity=scenario_capacity,
                minimum_roi=0.0,
                return_shadow=False,
            )
            scenario_random = build_baseline_policy(
                scenario, "random", small_cost * 0.50, seed=seed
            )
            opt_value = float(scenario_optimizer.expected_value)
            random_value_scenario = float(scenario_random.expected_value.sum())
            sensitivity_rows.append(
                {
                    "margin_multiplier": margin_multiplier,
                    "capacity_fraction": capacity_fraction,
                    "optimized_expected_value_inr": opt_value,
                    "random_expected_value_inr": random_value_scenario,
                    "incremental_value_vs_random_inr": opt_value - random_value_scenario,
                    "optimized_contacts": float(scenario_optimizer.assignments.user_id.nunique()),
                }
            )
    return BusinessCaseResult(
        candidates,
        policy_results,
        pd.DataFrame(sensitivity_rows),
        claim,
        canonical_optimizer,
        canonical_pacing,
    )
