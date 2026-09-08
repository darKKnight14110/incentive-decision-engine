# M4 learning and build record: data contracts and testing

M4 turns the M2/M3 data model into a build-time boundary. The pipeline now
checks the raw marketplace tables before they can be treated as trustworthy,
and checks the persisted modeling table before it can be consumed by causal
or policy code.

## Contract surface

`src/data/validate_data.py` defines executable contracts for all 11 raw tables
and for `eligible_users.parquet`. Each contract states:

- required columns and expected pandas-compatible types;
- nullability and numeric ranges;
- primary-key and logical-key uniqueness;
- foreign-key relationships;
- timestamp ordering and business reconciliations.

The raw checks include the required treatment enum (`no_offer`, `small_offer`,
or `large_offer`), positive order and refund amounts, and
`refund_amount_inr <= orders.gross_value_inr`. The source model uses
`variable_cost_rate` rather than a stored `margin_rate`; its configured range
is validated, while order contribution margin is checked by reconciliation.
Negative-margin orders are retained as warning-level guardrail inputs because
the generator intentionally creates them for marketplace stress testing.

The project uses three named action arms rather than the binary treatment
example in the generic learning plan. This matches the incentive decision
question and keeps the enum consistent across assignments, orders, offers, and
the processed table.

## Severity and failure behavior

`ValidationReport` exposes `errors`, `warnings`, `is_valid`, and a tabular
report. Structural violations are errors. Warnings preserve useful operational
signals without making the synthetic stress fixture impossible to build.
Calling `raise_if_invalid()` raises `DataContractError` with table and check
names, so a downstream notebook cannot accidentally proceed from an invalid
artifact.

The feature contract is enforced inside `build_feature_frame` and
`build_features` before the Parquet write. It requires the expected one-row
per-logical-assignment shape, rejects unexpected columns including
post-treatment source names, checks feature types/ranges, keeps only eligible
rows, and verifies the strict point-in-time condition:

```text
latest_pre_treatment_event_ts < decision_ts
```

The separate SQL quality view remains non-destructive and reports the known
raw defects. Contracts stop impossible data at the boundary; quality reports
explain defects that are intentionally preserved for analysis.

## Tests

The suite includes:

- coverage of every M2 table contract and executable schema DDL;
- a deliberate impossible monetary value and an orphan foreign key;
- a processed-feature corruption test that fails on event-at-decision leakage;
- a 12-user hand-built fixture with exact expected session funnel counts,
  signup-week retention rows, point-in-time order counts, and eligibility
  output;
- the existing generator, economics, SQL-grain, PIT, and reproducibility
  tests.

The fixture lives in `tests/test_sql_fixtures.py`. It is intentionally small
enough to inspect by hand and catches regressions that a large random dataset
could hide behind aggregate averages.

## Rebuild commands

```powershell
python -m src.reporting.metric_tree
python -m src.data.generate_marketplace --output-dir data/raw
python -m src.data.build_features --raw-dir data/raw --output-path data/processed/eligible_users.parquet --quality-report data/processed/data_quality_issues.csv
python -m src.data.validate_data --raw-dir data/raw --report-path data/processed/data_contract_report.csv
python -m pytest -q
```

`make build` and `make test` run the same gates where GNU Make is available.
The validator CLI exits successfully when it records warning-level issues and
supports `--fail-on-errors` for a hard command-line gate.

With the default seeded data, the contract report records the intentionally
duplicated assignment key as errors and negative-margin/exposure-timing
signals as warnings. The raw SQL quality report separately records duplicate
assignments, pre-signup orders, and negative margins. No raw row is silently
repaired.

## M4 boundary

M4 is complete when `pytest` is green, the feature build validates before
writing, and raw defects produce named, readable diagnostics. The next stage
can consume a stable modeling table, but it must still distinguish measured
randomized outcomes from simulated marketplace values before making any causal
or business-impact claim.
