# Incentive Decision Engine: recruiter one-pager

## One-line summary

Built a reproducible causal decision engine that turns randomized experiment
evidence into budget- and capacity-constrained promotion allocations.

## Why it is technically interesting

- Separates conversion propensity from heterogeneous treatment response.
- Uses SRM and balance diagnostics before interpreting randomized outcomes.
- Validates estimators against known ground truth, including confounding and poor overlap.
- Evaluates uplift on held-out randomized data with policy value, Qini/AUUC, and bootstrap intervals.
- Converts response estimates into redemption-adjusted contribution margin.
- Solves a multiple-choice knapsack with budget, contact, ROI, and city-hour constraints.
- Cross-checks HiGHS against an OR-Tools CP-SAT backend and a bounded exhaustive oracle.
- Uses an interview-defendable targeting architecture: leakage-safe segmentor,
  finite-horizon budget pacer, pluggable solver seam, and versioned assignment
  publisher.
- Treats marketplace interference as a design problem requiring cluster randomization.
- Includes point-in-time data contracts, persistent holdout, drift checks, rollout gates, and rollback rules.

## Evidence and honesty

The checked-in smoke experiment is intentionally conservative: +0.29
percentage points conversion ITT with a 95% interval from −0.33 to +0.91
points. That interval crosses zero, so no positive Criteo impact is claimed.

The separate synthetic marketplace business case is decision-shaped: at the
canonical 50% budget, the capacity-aware optimizer produces ₹2,038 expected
net contribution versus ₹723 for random allocation, or ₹5.26 more per eligible
user (95% user-bootstrap interval ₹4.18 to ₹6.47). This is a simulated
estimated illustration with explicit economics and capacity, not realized
impact. A geo-randomized pilot is the proposed validation step.

## Where to look

- Code: `src/experimentation`, `src/causal`, `src/policy`, `src/segmentation`, `src/orchestration`, `src/assignments`, `src/marketplace`, `src/monitoring`
- Data quality/PIT: `src/data`, `sql/`, `tests/`
- Decision artifacts: `reports/`, [`docs/business_case.md`](../docs/business_case.md), and `docs/executive_case_study.pdf`
- Interactive readout: `streamlit run app/dashboard.py`
