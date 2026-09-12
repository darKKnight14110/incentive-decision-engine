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
- Treats marketplace interference as a design problem requiring cluster randomization.
- Includes point-in-time data contracts, persistent holdout, drift checks, rollout gates, and rollback rules.

## Evidence and honesty

The checked-in smoke result is intentionally inconclusive: +0.29 percentage
points conversion ITT with a 95% interval from −0.33 to +0.91 points. The
synthetic economic policy therefore declines to spend when priced actions are
negative. No realized business impact is claimed.

## Where to look

- Code: `src/experimentation`, `src/causal`, `src/policy`, `src/marketplace`, `src/monitoring`
- Data quality/PIT: `src/data`, `sql/`, `tests/`
- Decision artifacts: `reports/` and `docs/executive_case_study.pdf`
- Interactive readout: `streamlit run app/dashboard.py`
