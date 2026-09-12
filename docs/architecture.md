# Interview-defendable targeting architecture

The repository now exposes the same *kind* of separation used in public
marketplace allocation systems: an orchestrator coordinates segmentation,
budget pacing, candidate scoring, constrained optimization, and assignment
publishing. This is an independent implementation based on public descriptions
of Uber's Tarot architecture, not copied proprietary code.

```text
pre-treatment user snapshot
        |
        v
segmentor -> opportunity table (user x action)
        |
        v
budget pacer -> solver backend (HiGHS default; CP-SAT seam is optional)
        |
        v
assignment publisher -> auditable delivery queue
```

## Components

- `src/segmentation/segmentor.py` contains a deterministic lifecycle
  segmentor and an optional train-only KMeans segmentor. Both reject
  post-treatment fields, so segmentation cannot leak exposure or outcomes.
- `src/policy/pacer.py` reconciles realized spend and predicted liability with
  the remaining horizon, returning a recommended cycle budget and a pause/run
  status.
- `src/policy/solver.py` provides a stable backend interface. SciPy/HiGHS is
  deterministic and offline-friendly; the CP-SAT adapter fails loudly when the
  optional dependency is absent rather than silently changing the solver.
- `src/orchestration/targeting.py` is the decision boundary that composes the
  pacer and solver against the shared candidate contract.
- `src/assignments/publisher.py` writes one-row-per-user assignments with
  deterministic IDs, model/policy versions, and a delivery-ready schema.

The business case calls this boundary at the canonical budget, while the full
policy grid and sensitivity analysis remain explicit and reproducible. Criteo
supplies measured incrementality; INR economics and capacity are synthetic
illustrations, clearly labelled in the reports.

## Why segmentation is optional

Rule-based lifecycle segments are the default because they are stable,
explainable, and easy to defend in an interview. Clustering is available for
discovery, but it must be fit on training rows only, versioned, and validated
for stability before it can influence a policy. A geographic cluster used for
interference testing is a different object from a customer segment and should
not be conflated with it.

## Provenance

The modular boundaries are informed by Uber's public engineering post on
multiple-knapsack allocation and the associated causal marketplace paper:

- <https://www.uber.com/ca/en/blog/solving-multiple-knapsack/>
- <https://arxiv.org/abs/2407.19078>
