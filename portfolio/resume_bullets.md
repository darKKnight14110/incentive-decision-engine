# Resume-ready bullets

## Full project bullet

Built an end-to-end incentive allocation engine using randomized-experiment
measurement, cross-fitted heterogeneous-treatment-effect models, redemption-
adjusted unit economics, and a multiple-choice knapsack allocator under budget,
contact, and marketplace-capacity constraints; added point-in-time data
contracts, held-out policy evaluation, staged rollout gates, and drift monitoring.

## Technical bullet

Implemented SRM/balance diagnostics, ITT and power analysis, constant/T/X/DR
learners, Qini/AUUC and randomized policy-value evaluation, known-ground-truth
estimator recovery, and SciPy/HiGHS constrained optimization in a reproducible
Python/DuckDB pipeline with 44 tests.

## Honest result bullet

Established a conservative decision rule on a deterministic smoke experiment:
the estimated conversion lift was +0.29pp with a 95% interval spanning zero,
so the configured economic policy withheld paid offers rather than claiming
unsupported incremental impact.

## Customization rule

Only replace the honest-result bullet with a percentage after running the full
Criteo reproduction and confirming that the held-out policy-value interval is
positive at a named matched budget.
