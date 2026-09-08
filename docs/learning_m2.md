# M2 learning and build record: data modeling and synthetic generation

## Purpose

The Criteo randomized dataset supports causal advertising analysis but does not
contain the marketplace entities and operational events needed by the incentive
decision. M2 supplies simulated plumbing for those fields without presenting
the simulation as measured business impact.

## What is implemented

`src/data/generate_marketplace.py` provides one seeded generator per table and a
`generate_marketplace(...)` orchestration function. The build creates:

1. `users`
2. `sessions`
3. `merchants`
4. `orders`
5. `offers`
6. `exposures`
7. `redemptions`
8. `cancellations`
9. `refunds`
10. `experiment_assignments`
11. `city_hour_capacity`

The command-line entry point writes CSV files and a `manifest.json` with the
seed, population, observation window, and row counts:

```powershell
python -m src.data.generate_marketplace --output-dir data/raw
```

## Modeling choices

- Users have a latent engagement score that drives session and order intensity,
  so the data has structure worth discovering.
- Events retain timezone-aware timestamps. Later SQL can enforce
  `event_ts < decision_ts` for point-in-time features.
- Orders choose merchants within the user's city and derive variable costs from
  merchant cost rates plus noise.
- Exposure, redemption, cancellation, and refund events are separate tables so
  treatment, cost, and post-treatment outcomes cannot be confused.
- City-hour capacity is modeled as context for the later marketplace extension.

## Deliberate quality warts

The generator injects approximately 0.3% duplicate assignment rows, a small
number of orders with `order_ts < signup_ts`, and negative-margin orders. These
are documented raw-data defects. M4 validation is expected to detect them; M2
does not silently repair them.

## Boundary with later modules

M2 defines grains, keys, relationships, timestamps, and the data-generating
process. M3 builds funnels, cohorts, rolling features, and point-in-time SQL;
M4 adds schema and leakage contracts. No causal effect or business-impact claim
comes from this synthetic dataset.
