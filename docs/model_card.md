# Model card: heterogeneous treatment-effect policy

**Intended use.** Rank eligible customers for an advertising/promotion policy
under a fixed budget. The Criteo model is a binary advertising response model;
multi-action offer decisions are demonstrated separately on synthetic data.

**Training and evaluation.** Features are the 12 anonymized pre-treatment
Criteo fields. Calibrated logistic regression and LightGBM are predictive
baselines; their log loss, Brier score, calibration error, PR-AUC, and seed
stability are diagnostics, not causal evidence. Training, validation,
cross-fitting, and final-test rows are disjoint. Full-data ITT and final policy
value stream every validated row, while model fitting is bounded by the
configured training cap recorded in the run manifest. Evaluation uses uplift
deciles, Qini/AUUC, randomized policy value, and fixed-policy bootstrap
intervals.

**Limitations.** Individual effects are estimates, not observed truth. The
bootstrap holds the fitted ranking fixed and does not include model-selection
uncertainty. Criteo exposure is post-assignment. Synthetic economics,
capacity, and rollout results are simulations, not realized impact. The
business-case headline uses the explicit assumptions in
`configs/economics.yaml`; it is useful for comparing decision logic and
uncertainty handling, not for forecasting a launch P&L.
