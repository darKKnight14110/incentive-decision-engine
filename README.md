# Incentive Decision Engine

An end-to-end foundation for deciding which customers should receive a
promotion when the business has a fixed budget and real operational
constraints.

The project is built around one business question:

> Given a fixed promotion budget, should each eligible customer receive no
> offer, a small offer, or a large offer to maximize incremental contribution
> margin without violating contact or marketplace guardrails?

This is not a churn model. It is a causal decision-system project. The core
distinction is between predicting who will buy and estimating who will buy
because of an intervention.

## Why this project matters

Promotion reporting often counts treated conversions as campaign success. That
can reward spending on customers who would have purchased anyway, hide negative
effects, and ignore the cost of the offer. A useful decision engine therefore
needs more than a classifier:

1. A clearly defined eligible population and decision timestamp.
2. Point-in-time-correct customer history.
3. Randomized measurement of incremental impact.
4. Unit economics that convert lift into contribution margin.
5. A constrained policy that respects budget, contact, and marketplace limits.
6. Evaluation that separates measured outcomes, model estimates, and simulated
   projections.

The current repository implements the product framing, unit-economics contract,
synthetic marketplace data model, SQL analytics foundation, and build-time data
contracts required before causal modeling and policy optimization can be
trusted.

## Resume significance

This project demonstrates the parts of applied data science that are easy to
miss in a model-only portfolio project:

- translating a growth problem into a decision, objective, denominator, and
  guardrails;
- building a relational event model with explicit table grains and keys;
- writing analytical SQL that avoids fan-out and preserves event timing;
- enforcing point-in-time feature construction with strict timestamp logic;
- separating predictive propensity from causal treatment response;
- converting incremental response into contribution-margin value after offer
  cost;
- making data defects observable instead of silently repairing them;
- producing a deterministic, tested rebuild from raw tables to a modeling
  dataset.

A truthful resume-ready description at the current stage is:

> Built a reproducible incentive-allocation data foundation with a seeded
> marketplace event generator, DuckDB analytical SQL, point-in-time customer
> features, unit-economics value logic, and data-quality tests for budgeted
> promotion decisions.

No business-impact percentage is claimed yet. The synthetic marketplace is for
pipeline and decision-system development, not evidence of realized impact.

## Product decision contract

| Item | Contract |
| --- | --- |
| Decision owner | Growth or CRM, with Finance owning budget and Operations owning capacity |
| Decision unit | One eligible customer at one `decision_ts` |
| Actions | `no_offer`, `small_offer`, `large_offer` |
| Primary objective | Incremental contribution margin per eligible customer |
| Outcome window | 14 days after assignment |
| Eligibility | Prior completed order, seven-day account age, active city, consent, not suppressed, and no contact in the prior 14 days |
| Hard constraints | One action per customer, budget, contact frequency, and later city-hour capacity |
| Honest result labels | Measured, estimated, or simulated |

The value contract is:

```text
value(i, a) = incremental_conversion(i, a)
              * expected_contribution_margin(i)
              - expected_offer_cost(i, a)
```

Offer cost is configured as either exposure cost or expected redemption cost in
[`configs/base.yaml`](<C:/Users/Varad S Pendse/Desktop/churnproject/configs/base.yaml>).

## What is implemented

### M0: business and measurement framing

The project defines the eligible population, actions, primary metric, outcome
window, guardrails, assumptions, and reporting language before modeling begins.
See [`docs/project_charter.md`](<C:/Users/Varad S Pendse/Desktop/churnproject/docs/project_charter.md>),
[`docs/metric_definition.md`](<C:/Users/Varad S Pendse/Desktop/churnproject/docs/metric_definition.md>),
and [`docs/assumptions_register.md`](<C:/Users/Varad S Pendse/Desktop/churnproject/docs/assumptions_register.md>).

### M1: unit economics

[`src/economics/unit_economics.py`](<C:/Users/Varad S Pendse/Desktop/churnproject/src/economics/unit_economics.py>)
implements expected offer cost, incremental value, cost per incremental order,
and ROI with denominator guards. This keeps campaign economics separate from
the treatment-effect estimator that will be added later.

### M2: synthetic marketplace data

[`src/data/generate_marketplace.py`](<C:/Users/Varad S Pendse/Desktop/churnproject/src/data/generate_marketplace.py>)
creates 11 seeded tables:

`users`, `sessions`, `merchants`, `orders`, `offers`, `exposures`,
`redemptions`, `cancellations`, `refunds`, `experiment_assignments`, and
`city_hour_capacity`.

The generator preserves timezone-aware event timestamps and intentionally
injects a small number of duplicate assignments, impossible order timestamps,
and negative-margin orders. These defects make the validation layer testable.
The logical schema is in [`sql/schema.sql`](<C:/Users/Varad S Pendse/Desktop/churnproject/sql/schema.sql>),
with grains and relationships documented in
[`docs/data_dictionary.md`](<C:/Users/Varad S Pendse/Desktop/churnproject/docs/data_dictionary.md>).

### M3: DuckDB analytical SQL

The SQL layer is organized as composable views:

- [`sql/product_metrics.sql`](<C:/Users/Varad S Pendse/Desktop/churnproject/sql/product_metrics.sql>)
  provides daily and weekly active users, session and user funnels,
  first-order and repeat-order metrics, and lifecycle segments.
- [`sql/retention_cohorts.sql`](<C:/Users/Varad S Pendse/Desktop/churnproject/sql/retention_cohorts.sql>)
  builds signup-week and first-order cohort views.
- [`sql/user_features.sql`](<C:/Users/Varad S Pendse/Desktop/churnproject/sql/user_features.sql>)
  builds pre-treatment session, recency, frequency, monetary, margin, and
  prior-contact features.
- [`sql/experiment_metrics.sql`](<C:/Users/Varad S Pendse/Desktop/churnproject/sql/experiment_metrics.sql>)
  summarizes assignment, exposure, redemption, order, cancellation, refund,
  and margin outcomes by treatment arm.
- [`sql/data_quality.sql`](<C:/Users/Varad S Pendse/Desktop/churnproject/sql/data_quality.sql>)
  reports duplicate keys, orphan records, invalid timestamps, impossible
  monetary values, join multiplication, and post-treatment leakage.

The feature build is implemented in
[`src/data/build_features.py`](<C:/Users/Varad S Pendse/Desktop/churnproject/src/data/build_features.py>).
It loads generated CSVs into DuckDB, executes the SQL assets in dependency
order, and writes one row per eligible user to Parquet.

### M4: data contracts and testing

[`src/data/validate_data.py`](<C:/Users/Varad S Pendse/Desktop/churnproject/src/data/validate_data.py>)
defines executable contracts for every raw marketplace table and for the
persisted `eligible_users` modeling table. The validator checks types,
nullability, ranges, uniqueness, referential integrity, timestamp ordering,
monetary reconciliation, treatment enums, and refund amounts that exceed the
linked order value. The feature contract also rejects unexpected or
post-treatment columns and enforces the strict point-in-time boundary.

The feature build fails before writing Parquet when its output contract is
invalid. The raw validator writes a named report to
`data/processed/data_contract_report.csv`; the non-destructive SQL quality view
continues to report intentional source defects separately. See
[`docs/learning_m4.md`](<C:/Users/Varad S Pendse/Desktop/churnproject/docs/learning_m4.md>)
for the contract design, severity rules, and test evidence.

## Point-in-time correctness

Every feature used for a decision at `decision_ts` is computed from events with
the strict predicate:

```sql
event_ts < decision_ts
```

This matters because a same-day date join or a `<=` predicate can admit events
that happened after the decision but before midnight. The implementation uses:

- `completed_ts` for completed-order history;
- `session_ts` for session history;
- `exposure_ts` for prior-contact history;
- a deterministic `ROW_NUMBER()` deduplication of logical assignment keys.

The final `eligible_users` view is a decision table, not a general customer
table. Its population is fixed before later policy comparisons so that a policy
cannot improve its result simply by changing who enters the denominator.

## Reproducible pipeline

### Requirements

- Python 3.11 or 3.12
- DuckDB
- pandas, NumPy, PyYAML, matplotlib, and pytest

Install the project in editable mode:

```bash
python -m pip install -e ".[dev]"
```

Generate the raw synthetic tables and rebuild the analytical dataset:

```bash
python -m src.data.generate_marketplace --output-dir data/raw
python -m src.data.build_features \
  --raw-dir data/raw \
  --output-path data/processed/eligible_users.parquet \
  --quality-report data/processed/data_quality_issues.csv
python -m src.data.validate_data \
  --raw-dir data/raw \
  --report-path data/processed/data_contract_report.csv
```

The equivalent project gates are:

```bash
make build
make test
```

On Windows, run the Python commands directly if `make` is unavailable.

## Verified example output

With the default seed and 1,000 generated users, the current rebuild produces:

- 11 raw CSV tables and a reproducibility manifest;
- 312 eligible-user rows in the Parquet modeling table;
- 312 distinct users in the modeling table;
- a quality report containing the intentionally injected duplicate-assignment,
  pre-signup-order, and negative-margin defects;
- a contract report with named structural errors and operational warnings;
- 37 passing tests covering generation, economics, SQL grain, point-in-time
  exclusion, schema contracts, fixture outputs, and build artifacts.

These numbers describe a local seeded simulation. They are not measured
business results.

## Architecture

```text
seeded marketplace tables
          |
          v
      DuckDB load
          |
          v
 product metrics + retention + experiment views
          |
          v
 point-in-time feature construction
          |
          v
 eligibility and quality checks
          |
          v
 eligible_users.parquet
          |
          v
 future causal estimation and constrained allocation
```

The two future-facing planes are deliberately separated from the current SQL
foundation:

1. Measurement will use a randomized advertising experiment to estimate
   incremental effects.
2. Learning will compare constant-effect, propensity, and heterogeneous-effect
   approaches on held-out randomized data.
3. Decisioning will convert effects to value and solve a budget- and
   capacity-constrained customer-action allocation.
4. Rollout will use a randomized validation slice and persistent holdout.

## Repository map

```text
configs/       Economic assumptions and hard policy constraints
docs/          Product charter, metric definitions, learning records, and data dictionary
sql/           Schema and analytical views
src/data/      Seeded data generation, DuckDB loading, feature build, validation
src/economics/ Unit-economics arithmetic
src/reporting/ Metric-tree artifact generation
tests/         Contract, generator, economics, SQL, and PIT tests
```

## Methodological safeguards

- Criteo is treated as randomized advertising data, not churn data.
- Synthetic marketplace outputs are labeled simulated.
- Assignment remains the experiment denominator; exposure and redemption are
  post-assignment descriptive measures.
- No post-treatment feature is used in the decision table.
- Funnel and feature joins are aggregated at their intended grain.
- Raw defects are reported rather than silently corrected.
- Classification metrics will not be presented as uplift evidence.
- Policy comparisons will use the same eligible population and matched budget.
- No resume-impact percentage is added until held-out policy evaluation and
  uncertainty analysis are complete.

## Project status

| Stage | Status |
| --- | --- |
| M0 business framing | Complete |
| M1 unit economics | Complete |
| M2 marketplace data model | Complete |
| M3 SQL analytics and PIT features | Complete |
| M4 full data-contract suite | Complete |
| Experiment analysis, uplift modeling, optimization, and rollout | Planned |

The next credible milestone is randomized experiment analysis, followed by
known-ground-truth estimator validation. The project should only claim an
incremental-margin improvement after a held-out policy evaluation supports it.
