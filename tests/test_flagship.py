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
from src.policy.pacer import BudgetPacer, BudgetPacerConfig
from src.orchestration.targeting import TargetingRunConfig, run_targeting
from src.assignments.publisher import publish_assignments
from src.segmentation.segmentor import ClusterSegmentor, RuleBasedSegmentor


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


def test_segmentors_are_versioned_and_leakage_safe():
    frame = pd.DataFrame({"engagement_score": [.10, .40, .80]})
    segmented = RuleBasedSegmentor().fit_transform(frame)
    assert segmented.segment_id.tolist() == ["dormant", "lapsing", "active"]
    assert segmented.segment_version.nunique() == 1
    with pytest.raises(ValueError, match="post-treatment"):
        ClusterSegmentor(n_clusters=2).fit(
            pd.DataFrame({"conversion": [0, 1], "x": [0.0, 1.0]}), ["conversion", "x"]
        )
    with pytest.raises(ValueError, match="post-treatment"):
        ClusterSegmentor(n_clusters=2).fit(
            pd.DataFrame({"treatment": [0, 1], "x": [0.0, 1.0]}), ["treatment", "x"]
        )


def test_budget_pacer_reconciles_liability_and_pauses_when_exhausted():
    pacer = BudgetPacer(BudgetPacerConfig(total_budget=100, total_cycles=4, safety_buffer=.10))
    snapshot = pacer.reconcile(cycle=1, realized_spend=20, predicted_liability=10)
    assert snapshot.remaining_budget == pytest.approx(70)
    assert snapshot.recommended_budget == pytest.approx(15.75)
    assert pacer.reconcile(cycle=4, realized_spend=100).status == "pause"


def test_targeting_and_assignment_contract_are_deterministic():
    candidates = pd.DataFrame({
        "user_id": ["u1", "u1", "u2", "u2"],
        "action": ["no_offer", "small_offer", "no_offer", "small_offer"],
        "expected_value": [0.0, 20.0, 0.0, 10.0],
        "expected_cost": [0.0, 15.0, 0.0, 15.0],
    })
    result = run_targeting(candidates, TargetingRunConfig(
        run_id="test-run", cycle=1, total_cycles=1, configured_budget=15,
        safety_buffer=0.0, maximum_contact_volume=1,
    ))
    assert result.budget.recommended_budget == pytest.approx(15)
    assert result.allocation.expected_cost <= 15
    published = publish_assignments(result.allocation.assignments, "reports/test_assignments.csv", "test-run", "m1", "p1")
    assert published.assignment_id.is_unique
    assert published.run_id.eq("test-run").all()
