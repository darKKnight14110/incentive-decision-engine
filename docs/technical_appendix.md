# Technical appendix

The pipeline has five contracts: validated data, randomized measurement,
cross-fitted response estimation, constrained allocation, and rollout control.
Every result is labeled measured, estimated, or simulated.

The Criteo ITT uses assignment as treatment and a difference in arm means with
normal-approximation uncertainty. SRM is checked first. Uplift models are fit
with disjoint folds and evaluated on held-out randomized rows. Policy value uses
inverse-probability weighting with the known treatment probability.

Synthetic marketplace candidates are priced with redemption-adjusted offer
costs and solved as a multiple-choice integer program. Budget comparisons use
the same eligible population and matched spend. The reported shadow-price
quantity is a finite-difference marginal-value proxy for the integer solution.

### Business case and claim boundary

The checked-in business result is a deterministic scenario, not a disguised
measurement of Criteo or a claim about a live marketplace. The assumptions are
versioned in `configs/economics.yaml`: ₹520 contribution margin per incremental
order, ₹18/₹35 face values, redemption rates of 0.35/0.55, a 50% contact cap,
and city-hour capacity equal to 28% of positive modeled demand. At the 50%
budget point, the optimizer is compared with random allocation over the same
500 users. A user-level bootstrap (500 resamples) gives the interval for the
expected-value difference. The resulting ₹6.88 per-user advantage (95% interval
₹6.16–₹7.71) is an estimated synthetic illustration. Before a real launch,
finance-approved margins and redemption costs must replace the scenario inputs,
and the response model must be validated in a geo-randomized pilot.
