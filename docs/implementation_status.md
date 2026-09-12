# Implementation status

The repository contains the complete offline implementation through the
causal, policy, marketplace, monitoring, and packaging layers. `make build`
runs the deterministic smoke path without network access. The full Criteo gate
has also been executed locally after the explicit download; the archive,
partition manifest, runtime, and peak-memory metadata are tracked separately
from the ignored raw data and Parquet intermediates.

The only quantities that can be measured from the public randomized dataset are
advertising assignment effects and held-out advertising policy value. INR
economics, multi-action offer effects, capacity, and rollout outcomes are
synthetic demonstrations and are labeled accordingly. The checked-in business
case is now decision-shaped: at the canonical 50% budget, the capacity-aware
optimizer yields ₹2,038 expected net contribution versus ₹723 for random on
250 synthetic users, a ₹5.26 per-user advantage (95% bootstrap interval ₹4.18
to ₹6.47). This is an estimated illustration under `configs/economics.yaml`,
not realized impact. The full-data Criteo claim is measured assignment ITT and
locked held-out policy value; its validation result selected the constant-effect
baseline, so the project explicitly reports that reliable heterogeneity was not
established.
