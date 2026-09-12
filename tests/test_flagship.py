from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.experimentation.criteo import partition_criteo, smoke_criteo, validate_criteo_frame
from src.experimentation.diagnostics import aa_pvalues, sample_ratio_mismatch
from src.experimentation.estimation import estimate_itt
from src.causal.estimators import difference_in_means, doubly_robust
from src.causal.simulate import generate_causal_data
from src.marketplace.geo_experiment import geo_experiment_design
from src.monitoring.drift import population_stability_index
from src.policy.optimize import optimize_allocation
from src.policy.business_case import run_business_case


def test_smoke_criteo_is_valid_and_partitioned_deterministically():
    data = smoke_criteo(500, 7)
    a, b = partition_criteo(data, 7), partition_criteo(data, 7)
    assert len(data) == 500
    assert np.array_equal(a.test_index, b.test_index)
    assert set(a.train_index) | set(a.validation_index) | set(a.test_index) == set(range(500))


def test_criteo_rejects_schema_and_post_treatment_column():
    data = smoke_criteo(200).drop(columns=["conversion"])
    with pytest.raises(ValueError): validate_criteo_frame(data)
    data = smoke_criteo(200); data["future_order"] = 1
    with pytest.raises(ValueError): validate_criteo_frame(data)


def test_srm_and_itt_recover_known_binary_effect():
    rng = np.random.default_rng(5)
    treatment = rng.binomial(1, .5, 5000)
    outcome = rng.binomial(1, .2 + .1*treatment)
    frame = pd.DataFrame({"treatment": treatment, "conversion": outcome})
    estimate = estimate_itt(frame, "conversion", expected_probability=.5, fail_on_srm=False)
    assert estimate.point == pytest.approx(.1, abs=.04)
    assert sample_ratio_mismatch(treatment, .5, .001).passed


def test_aa_pvalues_are_calibrated():
    pvalues = aa_pvalues(np.random.default_rng(2).binomial(1, .2, 1000), repetitions=100, seed=3)
    assert .02 < np.mean(pvalues < .05) < .12


def test_known_ground_truth_dr_estimator_is_close():
    data = generate_causal_data(1200, seed=3, effect="constant")
    x = data.frame[["x0", "x1", "x2", "x3"]].to_numpy()
    estimate = doubly_robust(x, data.frame.outcome, data.frame.treatment, data.frame.propensity)
    assert estimate == pytest.approx(data.true_ate, abs=.12)


def test_optimizer_obeys_budget_and_one_action_constraint():
    frame = pd.DataFrame({"user_id":["u1","u1","u2","u2"],"action":["no_offer","small_offer","no_offer","small_offer"],"expected_value":[0,30,0,20],"expected_cost":[0,50,0,50]})
    result = optimize_allocation(frame, 50, return_shadow=False)
    assert result.expected_cost <= 50
    assert result.assignments.user_id.is_unique


def test_geo_design_and_psi_are_finite():
    assert geo_experiment_design(10, .2, 100).minimum_detectable_effect > 0
    assert population_stability_index(np.arange(10), np.arange(10)) < .01


def test_business_case_is_reproducible_and_has_a_decision_shaped_claim():
    first = run_business_case(seed=11, n_users=40, bootstrap_repetitions=40)
    second = run_business_case(seed=11, n_users=40, bootstrap_repetitions=40)
    claim = first.canonical_claim
    assert claim == second.canonical_claim
    assert claim["optimized_expected_value_inr"] > claim["random_expected_value_inr"]
    assert claim["ci_low_inr_per_eligible_user"] > 0
    assert len(first.sensitivity) == 9
    assert first.sensitivity.incremental_value_vs_random_inr.min() > 0
    assert first.optimizer_result.assignments.user_id.is_unique
    assert first.optimizer_result.expected_cost <= float(
        first.candidates.loc[first.candidates.action == "small_offer", "expected_cost"].sum() * .5
    ) + 1e-8
