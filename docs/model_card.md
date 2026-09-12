# Model card: heterogeneous treatment-effect policy

**Intended use.** Rank eligible customers for an advertising/promotion policy
under a fixed budget. The Criteo model is a binary advertising response model;
multi-action offer decisions are demonstrated separately on synthetic data.

**Training and evaluation.** Features are the 12 anonymized pre-treatment
Criteo fields. Training, validation, cross-fitting, and final-test rows are
disjoint. Evaluation uses uplift deciles, Qini/AUUC, randomized policy value,
and bootstrap intervals. Predictive AUC is not treated as uplift evidence.

**Limitations.** Individual effects are estimates, not observed truth. The
bootstrap holds the fitted ranking fixed and does not include model-selection
uncertainty. Criteo exposure is post-assignment. Synthetic economics,
capacity, and rollout results are simulations, not realized impact. The
business-case headline uses the explicit assumptions in
`configs/economics.yaml`; it is useful for comparing decision logic and
uncertainty handling, not for forecasting a launch P&L.
