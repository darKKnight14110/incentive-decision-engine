# Incentive Decision Engine

An end-to-end data science project for deciding who should receive a
promotion when the objective is incremental contribution margin, not treated
conversion rate.

The repository combines randomized-experiment measurement, heterogeneous
treatment-effect estimation, unit economics, integer optimization, and
marketplace-capacity controls. It is designed as a reproducible portfolio
project: every headline number is tagged as measured, estimated, or simulated.

## Decision and results

The decision is whether to send no offer, a small offer, or a large offer to an
eligible customer under a fixed budget and operational constraints.

The checked-in offline run has two deliberately separate results:

1. **Smoke inference check.** On 12,000 deterministic, simulated
   Criteo-shaped randomized rows, the conversion ITT is **+0.29 percentage
   points** with a 95% interval of **−0.33 to +0.91 points**. The interval
   crosses zero, so the project does not claim positive advertising impact from
   this smoke fixture. The complete Criteo result is produced only by
   `make reproduce-full` after the explicit download.
2. **Business decision illustration.** On 250 deterministic synthetic
   marketplace users with explicit INR economics and city-hour capacity, the
   capacity-aware optimizer produces **₹2,038 expected net contribution at the
   canonical 50% budget versus ₹723 for random allocation**. The difference
   is **₹1,315 in aggregate, or ₹5.26 per eligible user**, with a user-bootstrap
   interval of **₹4.18 to ₹6.47 per user**. This is an estimated synthetic
   illustration, not realized business impact.

The business-case advantage remains positive across the checked-in sensitivity
grid for contribution margin at 75%, 100%, and 125% of the base assumption and
capacity at 20%, 28%, and 40% of positive modeled demand. See the exact values
in [the sensitivity table](reports/business_case_sensitivity.csv).

The second result makes the business decision concrete without pretending that
Criteo contains marketplace margins or delivery capacity. The assumptions are
in [`src/policy/business_case.py`](src/policy/business_case.py) and are the
first inputs to replace with validated unit economics in a production pilot.

## What was implemented

### Experiment and data layer

- Official Criteo v2.1 downloader/loader with source, SHA-256, schema, row
  count, and citation manifest.
- Strict validation of `f0`–`f11`, assignment, exposure, visit, and conversion.
- Deterministic stratified 60/20/20 train, validation, and final-test splits.
- SRM and balance diagnostics, A/A calibration, ITT with confidence intervals,
  and power/MDE calculations.
- Offline smoke data for clean-clone builds without network access.

### Causal modeling

- Calibrated logistic and LightGBM propensity baselines.
- Constant-effect, T-, X-, and cross-fitted doubly robust learners, with
  fold-level predictions and persisted model metadata.
- Known-ground-truth simulations for constant, heterogeneous, confounded, and
  poor-overlap data-generating processes.
- Qini/AUUC, uplift deciles, fixed-policy bootstrap intervals, and held-out
  randomized policy-value evaluation.
- Explicit separation of propensity prediction from incremental response.

### Value and constrained decisioning

- Redemption-adjusted offer cost and contribution-margin calculations.
- Treat-none, treat-all, random, propensity, uplift, net-value, and optimized
  policy comparisons at matched budgets and on the same eligible population.
- Multiple-choice integer optimization with SciPy/HiGHS for one action per
  user, budget, contact volume, ROI, segment, and city-hour capacity limits.
- Exhaustive-fixture and greedy/Lagrangian cross-checks, plus a discrete
  finite-difference shadow-price proxy.
- A synthetic multi-action business case with positive and negative actions,
  congestion-aware capacity, explicit assumptions, and bootstrap uncertainty.

### Rollout and delivery

- Eight-week rollout simulation with persistent holdout, validation launch,
  staged ramp gates, pause/rollback rules, retraining triggers, and delayed
  outcome monitoring.
- Drift, calibration, policy-mix, cancellation, refund, delivery-time, CPIO,
  budget-utilization, and expected-versus-realized value checks.
- Streamlit dashboard, experiment readout PDF, executive case study PDF,
  technical appendix, model card, geo-experiment memo, rollout plan, and a
  ten-minute interview deck.
- Four thin narrative notebooks that call reusable `src/` functions rather than
  hiding analysis in notebook cells.

## Start here

- [Experiment readout](reports/experiment_readout.pdf)
- [Executive case study](docs/executive_case_study.pdf)
- [Synthetic business case](docs/business_case.md)
- [Synthetic business claim](reports/business_case_claim.json)
- [Canonical assignment queue](reports/assignments.csv)
- [Matched-budget policy table](reports/business_case.csv)
- [Business-case sensitivity](reports/business_case_sensitivity.csv)
- [Optimizer parity benchmark](reports/optimizer_benchmark.json)
- [Architecture note](docs/architecture.md)
- [Technical appendix](docs/technical_appendix.md)
- [Model card](docs/model_card.md)
- [Rollout plan](docs/rollout_plan.md)
- [Interview deck](reports/interview_deck.pptx)
- [Streamlit dashboard](app/dashboard.py)
- [Resume bullets](portfolio/resume_bullets.md)

## Run the project

Install dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Run the deterministic offline build and tests:

```powershell
python -m src.pipeline --mode smoke --output-dir reports
python -m pytest -q
python -m src.reporting.claim_audit
python -m src.reporting.benchmark
```

On systems with GNU Make, the equivalent gates are:

```text
make build
make test
make audit-claims
```

To reproduce the public randomized experiment, download the raw Criteo file
explicitly and then run the full pipeline:

```powershell
python -m src.experimentation.criteo --download-dir data/raw/criteo
python -m src.pipeline --mode full --output-dir reports
```

Launch the dashboard with:

```powershell
streamlit run app/dashboard.py
```

Raw data, caches, trained models, and interim tables remain ignored. Generated
figures, reports, and manifests are reproducible from the configured seed.

## System design

```text
Criteo randomized data ──> SRM / ITT / held-out uplift ──> policy value
                                                              │
synthetic marketplace ──> INR economics ──> constrained optimizer ──> rollout
                                                              │
                                                capacity + monitoring controls
```

The two data sources are intentionally never joined. Criteo supplies measured
advertising incrementality. Synthetic marketplace data supplies multi-action
economics, capacity, interference, and rollout demonstrations.

## Interview-defendable targeting architecture

The decision engine follows a modular, public-architecture pattern: an
orchestrator coordinates a leakage-safe segmentor, a budget pacer, a pluggable
solver, and an idempotent assignment publisher. The implementation is inspired
by public Uber Tarot engineering descriptions, but contains no proprietary
code. See [the architecture note](docs/architecture.md) for the contracts and
trade-offs.

```text
pre-treatment snapshot -> segmentor -> user x action candidates
                                  -> budget pacer -> HiGHS optimizer
                                  -> versioned assignment queue
```

Rule-based lifecycle segments are the default because they are explainable and
stable. An optional KMeans segmentor is fit on training rows only and cannot
use exposure, redemption, conversion, cancellation, refund, or realized
margin fields. The solver boundary can accommodate CP-SAT in an environment
that explicitly installs OR-Tools; offline builds use deterministic SciPy/HiGHS.

## Repository layout

```text
src/experimentation/  Criteo loading, diagnostics, ITT, power
src/prediction/       calibrated propensity baselines
src/causal/           simulations, estimators, meta-learners, uplift metrics
src/policy/           value conversion, baselines, optimizer, business case
src/segmentation/     leakage-safe lifecycle and optional clustering segmentors
src/orchestration/    targeting run contract that composes pacing and solving
src/assignments/      deterministic, versioned assignment publisher
src/marketplace/      capacity and geo-experiment design
src/monitoring/       drift and rollout decisions
src/data/             seeded marketplace data, PIT features, validation
src/pipeline.py       reproducible smoke/full artifact generation
configs/              experiment, modeling, policy, economics, rollout settings
sql/                  schema, funnel, cohort, experiment, and quality views
tests/                data-contract, leakage, causal, optimizer, and smoke tests
docs/                 technical, experiment, model, rollout, and executive docs
reports/              checked-in figures, tables, PDFs, deck, and manifests
portfolio/            concise project summary and resume-ready framing
app/                  lightweight Streamlit decision dashboard
```

## Guardrails and limitations

- Assignment, not exposure, is the causal treatment in Criteo.
- Features are strictly pre-treatment; post-assignment exposure is descriptive
  only.
- Predictive propensity metrics are diagnostics, not uplift evidence.
- Policy comparisons use identical users and matched budgets.
- Individual treatment effects are estimates, not observed truth.
- Bootstrap intervals hold the fitted ranking fixed and exclude model-selection
  uncertainty.
- Synthetic economics, capacity, interference, and rollout outcomes are not
  measured marketplace impact.
- A real launch requires validating offer costs, margins, response, and
  city-hour capacity in a geo-randomized pilot behind a persistent holdout.
