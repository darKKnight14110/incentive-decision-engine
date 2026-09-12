# Implementation status

The repository contains the complete offline implementation through the
causal, policy, marketplace, monitoring, and packaging layers. `make build`
runs the deterministic smoke path without network access. Full Criteo output is
opt-in: run `make download-criteo`, then `make reproduce-full`.

The only quantities that can be measured from the public randomized dataset are
advertising assignment effects and held-out advertising policy value. INR
economics, multi-action offer effects, capacity, and rollout outcomes are
synthetic demonstrations and are labeled accordingly. The checked-in business
case is now decision-shaped: at the canonical 50% budget, the capacity-aware
optimizer yields ₹2,038 expected net contribution versus ₹723 for random on
250 synthetic users, a ₹5.26 per-user advantage (95% bootstrap interval ₹4.18
to ₹6.47). This is an estimated illustration under `configs/economics.yaml`,
not realized impact. The checked-in Criteo result is a simulated RCT-shaped
smoke fixture; a full-data claim is emitted only after `make reproduce-full`
records the archive manifest and partitioned run.
