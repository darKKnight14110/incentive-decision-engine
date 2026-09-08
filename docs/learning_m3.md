# M3 learning and build record: SQL analytics and point-in-time features

## What is implemented

The SQL layer runs in DuckDB through `src/data/build_features.py` and is split
into dependency-ordered view files:

- `sql/product_metrics.sql`: daily and weekly active users, session and user
  funnel conversion/drop-off, first-order/repeat-order metrics, and lifecycle
  segments.
- `sql/retention_cohorts.sql`: signup-week retention and first-order cohorts.
- `sql/user_features.sql`: window-based pre-treatment RFM/session features and
  the eligible-user decision table.
- `sql/experiment_metrics.sql`: assignment, exposure, redemption, outcome, and
  treatment-arm summaries over the closed 14-day outcome window.
- `sql/data_quality.sql`: duplicate, orphan, timestamp, monetary, join-grain,
  and post-treatment leakage diagnostics.

## Grain and fan-out rules

The raw tables have different grains, so metrics aggregate each event table to
the target grain before combining them. In particular, orders are not joined
directly to sessions for funnel counts. The session funnel stays at session
grain; the completed-order stage is exposed separately at user grain because
the source schema does not contain a `session_id` on orders.

Assignments are deduplicated by logical `(user_id, experiment_id)` key with a
deterministic `ROW_NUMBER()` tie-break. This keeps raw duplicate assignments
visible to quality reporting without allowing them to multiply features or
experiment denominators.

## Point-in-time contract

The decision timestamp is `experiment_assignments.assignment_ts`. User features
use only events satisfying the strict predicate `event_ts < decision_ts`:

- completed orders use `completed_ts`, not only `order_ts`;
- sessions use `session_ts`;
- prior contact uses `exposure_ts`.

The equality case is intentionally excluded. The `pre_treatment_event_audit`
view records the latest source event used by the feature block, and the quality
layer reports any candidate where that timestamp is at or after the decision.
Eligibility is a rule layer applied after feature construction: prior completed
order, seven-day account age, active city, consent, not suppressed, and no
contact in the prior 14 days.

## Rebuild and outputs

```powershell
python -m src.data.generate_marketplace --output-dir data/raw
python -m src.data.build_features --raw-dir data/raw --output-path data/processed/eligible_users.parquet --quality-report data/processed/data_quality_issues.csv
```

The build is deterministic for the generator seed. It produces one row per
eligible user at the treatment timestamp and a separate quality report. The
quality report is intentionally non-destructive: M2 defects are surfaced before
later validation work instead of being silently repaired.

## Boundaries

The synthetic tables support SQL and business-plumbing development. They are
not evidence of realized promotion impact. Assignment-based causal estimates
and any Criteo analysis remain separate from this synthetic data source.
