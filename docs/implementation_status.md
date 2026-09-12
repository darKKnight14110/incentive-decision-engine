# Implementation status

The repository contains the complete offline implementation through the
causal, policy, marketplace, monitoring, and packaging layers. `make build`
runs the deterministic smoke path without network access. Full Criteo output is
opt-in: run `make download-criteo`, then `make reproduce-full`.

The only quantities that can be measured from the public randomized dataset are
advertising assignment effects and held-out advertising policy value. INR
economics, multi-action offer effects, capacity, and rollout outcomes are
synthetic demonstrations and are labeled accordingly.
