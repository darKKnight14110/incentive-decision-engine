# Incentive Decision Engine

**End-to-end causal decision system for budget-constrained promotion targeting.**

This project answers a product question that a propensity model cannot answer:

> Given a fixed promotion budget, which eligible customers should receive no
> offer, a small offer, or a large offer to maximize incremental contribution
> margin while respecting contact and marketplace constraints?

## Recruiter snapshot

| Dimension | Evidence in this repository |
| --- | --- |
| Product decision | Incremental contribution margin per eligible customer, not treated conversion rate |
| Experimentation | Criteo randomized advertising data, SRM/balance checks, ITT, confidence intervals, power/MDE |
| Causal ML | Constant-effect, T-, X-, and cross-fitted DR learners; Qini, AUUC, uplift deciles, policy value |
| Decisioning | Redemption-adjusted unit economics and multiple-choice knapsack optimization |
| Marketplace | City-hour capacity, delivery/cancellation guardrails, cluster-randomized validation design |
| Production thinking | Point-in-time feature contracts, drift monitoring, persistent holdout, staged rollout and rollback |
| Stack | Python, pandas, NumPy, SciPy, scikit-learn, DuckDB, SQL, Streamlit, matplotlib |

### What the current evidence says

The checked-in smoke run is deliberately conservative. On 12,000 deterministic
Criteo-shaped randomized rows, the estimated conversion ITT is **+0.29pp** with
a 95% interval of **−0.33pp to +0.91pp**. Because the interval crosses zero, the
repository makes no positive business-impact claim. Under the configured
synthetic INR economics, the matched-budget optimizer selects no paid offer when
all priced actions have negative expected net value. That is the intended
decision behavior, not a hidden failure.

Full Criteo reproduction is available but opt-in because the public raw file is
large and is not redistributed here. Criteo results are advertising
incrementality; marketplace economics and capacity results are simulated.

## Start here

- [Recruiter one-pager](portfolio/recruiter_one_pager.md)
- [Resume-ready bullets](portfolio/resume_bullets.md)
- [Executive case study PDF](docs/executive_case_study.pdf)
- [Technical appendix](docs/technical_appendix.md)
- [Experiment readout](reports/experiment_readout.pdf)
- [Interview deck](reports/interview_deck.pptx)
- [Model card](docs/model_card.md)
- [Rollout plan](docs/rollout_plan.md)
- [Dashboard](app/dashboard.py)

## Run it

Install the project and development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Run the deterministic offline smoke pipeline on Windows:

```powershell
python -m src.reporting.metric_tree
python -m src.data.generate_marketplace --output-dir data/raw
python -m src.data.build_features --raw-dir data/raw --output-path data/processed/eligible_users.parquet --quality-report data/processed/data_quality_issues.csv
python -m src.data.validate_data --raw-dir data/raw --report-path data/processed/data_contract_report.csv
python -m src.pipeline --mode smoke --output-dir reports
python -m pytest -q
```

The Makefile provides equivalent `build`, `test`, `download-criteo`,
`reproduce-full`, and `test-full` targets on systems with GNU Make.

To reproduce the public randomized experiment:

```powershell
python -m src.experimentation.criteo --download-dir data/raw/criteo
python -m src.pipeline --mode full --output-dir reports
```

Raw data, caches, and processed tables remain ignored. Each run writes a
manifest with seeds, row counts, input hashes, configuration, and runtime
metadata.

## System design

```text
synthetic marketplace tables ──┐
                               ├─ SQL/PIT feature contract ──┐
Criteo randomized data ───────┘                              │
                                                             ▼
                 experiment measurement → causal response estimation
                                             │
                                             ▼
                    INR value model → matched-budget policy comparison
                                             │
                                             ▼
                   constrained allocation → capacity-aware rollout control
```

The two data sources are intentionally never joined. Criteo supports measured
advertising incrementality and held-out policy evaluation. The synthetic
marketplace supports multi-action offers, economics, capacity, interference,
and rollout demonstrations.

## Repository layout

```text
portfolio/       recruiter one-pager and resume bullets
configs/         economic, experiment, modeling, policy, and rollout settings
src/data/        seeded generation, DuckDB loading, PIT features, validation
src/analytics/   reusable funnel, lifecycle, and cohort helpers
src/experimentation/  Criteo loading, diagnostics, ITT, power/MDE
src/prediction/  calibrated propensity baselines
src/causal/      DGPs, estimators, meta-learners, uplift/policy metrics
src/policy/      value conversion, baselines, constrained optimizer
src/marketplace/ capacity and geo-experiment design
src/monitoring/  drift and rollout decisions
src/pipeline.py  reproducible smoke/full artifact generation
sql/             schema, funnels, cohorts, features, experiment, quality views
tests/           44 contract, causal, optimizer, and pipeline tests
docs/            metric contract, model card, rollout, technical, and executive docs
reports/         checked-in figures, PDFs, deck, comparison tables, and manifests
app/             lightweight Streamlit decision dashboard
```

## Methodological guardrails

- Assignment, not exposure, is the Criteo causal treatment.
- Every modeling feature is strictly pre-treatment: `event_ts < decision_ts`.
- Predictive propensity metrics are not presented as uplift evidence.
- Policy comparisons use the same eligible population and matched budgets.
- Individual treatment effects are estimates, not observed truth.
- Bootstrap intervals hold the fitted ranking fixed and exclude model-selection uncertainty.
- Synthetic financial, capacity, and rollout outputs are labeled simulated.
- A persistent holdout is carved before allocation; rollback and retraining thresholds are preconfigured.

## Resume positioning

Use the bullets in [portfolio/resume_bullets.md](portfolio/resume_bullets.md).
Do not add a percentage improvement unless a full-data held-out policy-value
interval supports it. The current smoke evidence supports a defensible
“established no reliable positive lift under these assumptions” conclusion, not
an impact claim.
