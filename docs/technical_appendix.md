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
