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

## Business result bullet

Built a capacity-aware synthetic marketplace scenario in which the optimized
50%-budget policy generated ₹2,038 expected contribution margin versus ₹723
for random allocation, a ₹1,315 aggregate difference (₹5.26 per eligible user;
95% bootstrap interval ₹4.18–₹6.47), with all economics and capacity inputs
explicitly versioned and labelled as simulated.

## Measurement caveat bullet

On the deterministic Criteo smoke fixture, estimated conversion ITT was +0.29pp
with a 95% interval spanning zero; retained the null result and specified a
geo-randomized pilot rather than claiming unsupported advertising impact.

## Customization rule

Do not present the synthetic business-case result as realized impact. Replace
or supplement it with a production percentage only after running the full
Criteo reproduction and confirming a positive held-out policy-value interval
at a named matched budget.
