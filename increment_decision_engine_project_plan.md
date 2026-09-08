<!--
  Project plan for Varad Pendse.
  Purpose: flagship resume/portfolio project for product data science,
  decision science, marketplace science, and consulting analytics roles.
  Demonstrates the metrics -> experimentation -> causal ML -> policy
  optimization chain used by tech-first consumer and marketplace firms.
  Feed this file to a coding agent as the implementation specification;
  work from top to bottom, one phase at a time, committing after each.
-->

# Increment: Incentive Allocation & Budget-Constrained Decision Engine

**Business framing:** "We have a fixed promotion budget this quarter. Which eligible customers should receive an offer, which offer should they receive, and how much incremental contribution margin will the policy generate?"

## Goal
Build a case study that connects the complete product data science decision chain, rather than presenting disconnected notebooks:
1. Define the product objective, metric tree, eligibility rules, and guardrails
2. Build a point-in-time-correct analytical dataset using SQL
3. Analyze a randomized promotion experiment and estimate incremental impact
4. Predict baseline behavior as a deliberately naive targeting benchmark
5. Estimate **who benefits from intervention** using heterogeneous treatment-effect models
6. Convert treatment effects into a budget- and capacity-constrained targeting policy
7. Extend the policy to a two-sided marketplace with supply constraints and interference
8. Design an online rollout, persistent holdout, and monitoring framework

Every phase must produce a business-readable artifact: at least one decision-relevant chart and a short plain-language conclusion. The final repository should read as an end-to-end product decision, not as a collection of model demonstrations.

## Core decision

For each eligible customer `i`, choose an action `a` from:

```text
no_offer / small_offer / large_offer
```

Estimate the net value of each action as:

```text
value(i, a) = predicted_incremental_conversion(i, a)
              * expected_contribution_margin(i)
              - expected_offer_cost(i, a)
```

Choose actions that maximize total expected incremental contribution margin subject to campaign budget, contact-volume, frequency-cap, and marketplace-capacity constraints.

## Data strategy

Use two clearly separated data sources. Do not pretend the public experimental dataset is a churn dataset.

| Dataset | Purpose |
|---|---|
| Criteo Uplift Prediction Dataset | Primary randomized experiment for treatment-effect estimation and offline policy evaluation |
| Synthetic marketplace event data | SQL, funnels, retention, unit economics, multi-action incentives, supply constraints, and monitoring |

The Criteo treatment is an advertising exposure and its outcomes are visits/conversions. Frame it as promotion or advertising incrementality. Use synthetic data only where the public dataset does not contain the necessary business fields, and label all simulated results explicitly.

## Tech stack

| Layer | Tool |
|---|---|
| Language | Python 3.11 |
| Analytical database | DuckDB; PostgreSQL optional |
| Data processing | SQL, pandas or Polars |
| Prediction | scikit-learn / LightGBM |
| Experimentation | scipy / statsmodels; custom power and SRM checks |
| Causal estimation | EconML or custom meta-learners with scikit-learn |
| Optimization | PuLP or OR-Tools |
| Validation | pytest, Pandera or equivalent data-contract checks |
| Reporting | Jupyter or marimo, matplotlib/seaborn/Plotly |
| Decision interface | Streamlit, kept deliberately lightweight |

Do not add tools merely to make the stack look larger. Prefer transparent implementations and defensible methodology.

## Repository structure

```text
increment-decision-engine/
|-- README.md
|-- pyproject.toml
|-- configs/
|   |-- base.yaml
|   `-- policy_constraints.yaml
|-- data/
|   |-- raw/                     # gitignored
|   |-- interim/                 # gitignored
|   `-- processed/               # gitignored except tiny examples
|-- sql/
|   |-- schema.sql
|   |-- product_metrics.sql
|   |-- retention_cohorts.sql
|   |-- experiment_metrics.sql
|   `-- user_features.sql
|-- src/
|   |-- data/
|   |   |-- generate_marketplace.py
|   |   |-- build_features.py
|   |   `-- validate_data.py
|   |-- analytics/
|   |   |-- metrics.py
|   |   `-- cohorts.py
|   |-- experimentation/
|   |   |-- diagnostics.py
|   |   |-- estimation.py
|   |   `-- power.py
|   |-- prediction/
|   |   `-- propensity.py
|   |-- causal/
|   |   |-- meta_learners.py
|   |   |-- dr_learner.py
|   |   `-- evaluation.py
|   |-- policy/
|   |   |-- value.py
|   |   |-- baselines.py
|   |   `-- optimize.py
|   |-- marketplace/
|   |   |-- capacity.py
|   |   `-- geo_experiment.py
|   `-- monitoring/
|       |-- drift.py
|       `-- realized_value.py
|-- notebooks/
|   |-- 01_product_diagnostics.ipynb
|   |-- 02_experiment_analysis.ipynb
|   |-- 03_uplift_and_policy.ipynb
|   `-- 04_marketplace_extension.ipynb
|-- app/
|   `-- dashboard.py
|-- docs/
|   |-- project_charter.md
|   |-- metric_definition.md
|   |-- experiment_design.md
|   |-- model_card.md
|   |-- rollout_plan.md
|   `-- executive_case_study.pdf
|-- reports/
|   |-- figures/
|   `-- experiment_readout.pdf
`-- tests/
```

Keep notebooks thin. Reusable transformations, estimators, evaluation, and optimization logic belong in `src/`; notebooks should call those functions and communicate findings.

## Phase 0 - Business framing and measurement contract

- [x] Define the eligible customer population and decision timestamp
- [x] Define the available actions: no offer, small offer, and large offer
- [x] Define the outcome window and attribution window
- [x] Create a metric tree rooted in incremental contribution margin
- [x] Define primary metric: incremental contribution margin per eligible customer
- [x] Define secondary metrics: conversion, repeat purchase, average order value, and cost per incremental order
- [x] Define guardrails: cancellation rate, refund rate, negative-margin orders, delivery time, and excessive contact frequency
- [x] Separate measured outcomes, model estimates, and simulated projections in the reporting language
- [x] Create an assumptions register covering margin, offer redemption, interference, and delayed outcomes

**Output:** `docs/project_charter.md`, `docs/metric_definition.md`, metric-tree figure, and one-paragraph decision statement.

**Gate:** The business problem, decision, metric, constraints, and possible harms can be explained without mentioning a model.

## Phase 1 - Marketplace data model and product analytics

- [x] Generate realistic synthetic tables for users, sessions, merchants, orders, offers, exposures, cancellations, refunds, and experiment assignments
- [x] Preserve event timestamps and treatment timestamps so point-in-time correctness can be tested
- [x] Load the synthetic data into DuckDB
- [x] Document the grain and primary key of every table
- [x] Build funnel metrics from session to completed order
- [x] Build signup and first-order retention cohorts
- [x] Calculate recency, frequency, monetary value, and historical contribution margin
- [x] Segment users into new, active, lapsing, dormant, and resurrected lifecycle states
- [ ] Diagnose where an incentive intervention could plausibly create value

**Output:** database schema, data dictionary, funnel chart, retention heat map, lifecycle segmentation, and a one-page product diagnosis.

**Gate:** Every feature used later can be shown to have existed before treatment assignment, and every metric has an explicit numerator, denominator, grain, and time window.

## Phase 2 - SQL analytical layer and data quality

- [x] Implement daily/weekly active-user queries
- [x] Implement funnel conversion and drop-off queries
- [x] Implement cohort-retention queries
- [x] Implement first-order and repeat-order queries
- [x] Implement rolling recency, frequency, and margin features with window functions
- [x] Implement treatment exposure, redemption, and outcome queries
- [x] Build one row per eligible user at the treatment timestamp
- [x] Add checks for duplicate assignments, invalid timestamps, missing keys, impossible monetary values, and post-treatment leakage
- [x] Verify that joins do not multiply user, order, or experiment counts

**Output:** tested SQL transformation layer and a point-in-time-correct modeling table.

**Gate:** The analytical dataset can be rebuilt from raw tables with one command, and all data-contract tests pass.

## Phase 3 - Randomized experiment analysis

- [ ] Download and document the Criteo Uplift Prediction Dataset
- [ ] Confirm treatment/control counts and outcome definitions
- [ ] Run a sample-ratio-mismatch test
- [ ] Check pre-treatment feature balance without using balance as a reason to re-match randomized groups
- [ ] Estimate the intent-to-treat effect on visits and conversions
- [ ] Report absolute lift, relative lift, incremental conversions, standard errors, and confidence intervals
- [ ] Use regression adjustment only as a precision-improvement comparison
- [ ] Pre-specify a limited set of heterogeneous-effect segments
- [ ] Calculate power and minimum detectable effect for a future experiment
- [ ] Write a multi-arm experiment design for no offer, small offer, and large offer

Do not use propensity-score matching as the primary validation method. Randomization is the identification strategy.

**Output:** experiment readout, balance/SRM diagnostics, treatment-effect chart, power analysis, and ship/do-not-ship recommendation.

**Gate:** The recommendation accounts for uncertainty, effect size, business value, guardrails, representativeness, and experiment validity.

## Phase 4 - Propensity model as a naive targeting baseline

- [ ] Train a calibrated logistic-regression baseline
- [ ] Train a LightGBM or gradient-boosting comparator
- [ ] Use a clean validation/test split that preserves treatment/outcome representation; use temporal splitting for synthetic longitudinal data
- [ ] Report ROC-AUC, PR-AUC, log loss, Brier score, and calibration
- [ ] Create lift and calibration plots
- [ ] Define naive policies that target highest predicted outcome probability or highest predicted inactivity risk
- [ ] Document why outcome propensity is not an estimate of treatment response

**Output:** calibrated propensity scores, benchmark policy, model diagnostics, and a short note titled `Why propensity is not uplift`.

**Gate:** The distinction between `P(Y=1|X)` and `E[Y(1)-Y(0)|X]` is clear, and no predictive metric is presented as evidence of causal policy value.

## Phase 5 - Causal estimator validation on known ground truth

- [ ] Generate simulated data with a known constant treatment effect
- [ ] Generate simulated data with known heterogeneous treatment effects
- [ ] Generate a confounded observational treatment assignment
- [ ] Generate a poor-overlap scenario
- [ ] Compare naive difference, regression adjustment, propensity weighting, and doubly robust estimation
- [ ] Plot treatment propensity and overlap diagnostics
- [ ] Measure estimator bias and interval coverage across repeated simulations
- [ ] Create a deliberately biased observational sample from randomized data
- [ ] Compare observational estimates with the randomized experimental benchmark
- [ ] Document assumptions using a causal DAG

**Output:** estimator-recovery benchmark, overlap diagnostics, causal DAG, and experimental-versus-observational comparison.

**Gate:** The implementation recovers known effects under valid assumptions and visibly fails or becomes uncertain when overlap or confounding assumptions are violated.

## Phase 6 - Heterogeneous treatment-effect modeling

- [ ] Implement a constant-treatment-effect policy baseline
- [ ] Implement a T-learner
- [ ] Implement an X-learner
- [ ] Implement a DR-learner or causal forest with cross-fitting
- [ ] Prevent preprocessing and model-selection leakage across folds
- [ ] Evaluate on held-out randomized data using uplift by decile, Qini, and AUUC
- [ ] Estimate policy value using an appropriate randomized or doubly robust estimator
- [ ] Bootstrap uncertainty for uplift curves and policy value
- [ ] Check stability across random seeds and important pre-treatment segments
- [ ] Treat Persuadables, Sure Things, Lost Causes, and Do-Not-Disturbs as modeled latent segments, not observed customer types
- [ ] Select the final model based on defensibility, stability, and decision value rather than complexity

**Output:** Qini/AUUC comparison, uplift-decile chart, policy-value estimates, stability analysis, and `docs/model_card.md`.

**Gate:** The chosen uplift model beats simple policies on held-out policy value with reported uncertainty, or the report honestly concludes that reliable heterogeneity was not established.

## Phase 7 - Incremental value and constrained policy optimization

- [ ] Convert treatment effects into expected incremental contribution margin
- [ ] Model offer cost using redeemed-offer cost where appropriate, not merely exposure cost
- [ ] Implement treat-none, treat-all, random, propensity, uplift, and net-value policies
- [ ] Formulate the customer-action decision as a binary/integer optimization problem
- [ ] Add total budget constraint
- [ ] Add maximum contact-volume constraint
- [ ] Add one-action-per-customer constraint
- [ ] Add contact-frequency cap
- [ ] Add optional minimum expected ROI and segment constraints
- [ ] Evaluate policies across multiple budget levels
- [ ] Report incremental conversions, expected profit, cost per incremental order, ROI, and uncertainty
- [ ] Show marginal value of additional campaign budget

**Output:** profit-versus-budget curve, policy comparison table, allocation diagnostics, and final targeting recommendation.

**Gate:** The optimizer is compared with realistic simple baselines at matched budgets, and the headline result is a decision metric rather than a model metric.

## Phase 8 - Two-sided marketplace extension

- [ ] Simulate city-hour demand, merchant capacity, delivery-partner supply, preparation time, delivery time, cancellations, and contribution margin
- [ ] Show how an individually profitable promotion can overload local supply
- [ ] Add city-hour incremental-order capacity to the policy optimizer
- [ ] Add delivery-time, cancellation, or utilization guardrails
- [ ] Compare unconstrained customer targeting with capacity-aware targeting
- [ ] Analyze spillovers and explain why SUTVA may fail in a marketplace
- [ ] Design a geographic or cluster-randomized validation experiment
- [ ] Document short-run versus equilibrium effects

Keep this extension compact. It should demonstrate marketplace reasoning, not become a full dispatch simulator.

**Output:** marketplace metric tree, capacity-aware policy comparison, city-hour allocation chart, and geographic experiment memo.

**Gate:** The analysis explains when customer-level uplift is insufficient because treatment changes marketplace conditions for other users.

## Phase 9 - Rollout, monitoring, and realized impact

- [ ] Design a 5% randomized validation rollout
- [ ] Define 20%, 50%, and full-ramp decision gates
- [ ] Preserve a persistent randomized holdout
- [ ] Define rollback thresholds for primary and guardrail metrics
- [ ] Monitor realized incremental contribution margin and cost per incremental order
- [ ] Monitor treatment allocation, budget utilization, feature drift, calibration drift, and policy drift
- [ ] Account for delayed conversions and incomplete outcome windows
- [ ] Define model/policy retraining triggers
- [ ] Separate expected offline value from experimentally realized value
- [ ] Add batch-scoring and monitoring tests

**Output:** `docs/rollout_plan.md`, monitoring specification, alert thresholds, and simulated rollout dashboard.

**Gate:** A reader can determine what would cause the campaign to ramp, pause, roll back, or retrain.

## Phase 10 - Packaging and interview artifacts

- [ ] Write the README with the business decision and headline result before technical implementation details
- [ ] Produce a two-page executive case study using situation -> analysis -> recommendation -> impact -> risks
- [ ] Produce a technical appendix covering estimators, assumptions, validation, and limitations
- [ ] Export the experiment readout as a PDF
- [ ] Build a lightweight dashboard with budget selection and policy comparison
- [ ] Create a ten-minute interview presentation
- [ ] Add reproducible setup instructions and a small example dataset
- [ ] Ensure all tables and charts label experimental, estimated, and simulated quantities correctly
- [ ] Remove unused notebooks, dependencies, generated files, and unsupported claims
- [ ] Clean the commit history and tag a `v1.0` release

**Output:** portfolio-ready repository, executive case study, experiment readout, decision dashboard, and interview presentation.

**Gate:** The complete project can be presented without opening the code, and every important causal or financial claim can be traced to its identification strategy, estimator, assumptions, and uncertainty.

## Optional companion case - City-level demand forecasting

Keep forecasting separate from the core causal-policy narrative. Build it only after the flagship project is complete.

- [ ] Forecast daily orders by city for staffing/capacity planning
- [ ] Use rolling-origin validation; never random train/test splitting
- [ ] Compare last-value and seasonal-naive baselines with at least one learned model
- [ ] Include calendar, holiday, and promotion features without future leakage
- [ ] Report MAE/WAPE, bias, peak-period error, and prediction-interval coverage
- [ ] Translate forecast errors into asymmetric operational costs
- [ ] Produce a two-page capacity-planning recommendation

**Output:** compact forecasting case that fills a generalist DS portfolio gap without bloating the main project.

## Required policy comparisons

Every final result must compare the same eligible population and matched campaign constraints:

| Policy | Decision rule |
|---|---|
| Treat none | No eligible customer receives an offer |
| Treat all | Every eligible customer receives the same offer |
| Random | Random eligible customers until the budget is exhausted |
| Propensity | Highest predicted outcome probability or inactivity risk |
| Uplift | Highest predicted incremental response |
| Net value | Highest predicted incremental contribution margin |
| Optimized | Globally optimal feasible allocation under all constraints |

## Required methodological safeguards

- [ ] No post-treatment variables in model features
- [ ] No matching used to manufacture balance in randomized data
- [ ] No use of classification AUC as an uplift metric
- [ ] No evaluation on training data
- [ ] No individual causal effects presented as observed truth
- [ ] No policy comparison with unequal budgets unless clearly labeled
- [ ] No unqualified causal claim from observational data
- [ ] No simulated financial result described as realized business impact
- [ ] No single point estimate without uncertainty where uncertainty is estimable
- [ ] No complex estimator accepted without a simple benchmark

## Success criteria

- The SQL layer produces a tested, point-in-time-correct analytical dataset
- The randomized experiment analysis yields a defensible incremental-impact estimate
- The uplift model is evaluated using held-out causal/policy metrics rather than predictive AUC
- The optimized policy is compared with random, treat-all, propensity, and uplift baselines at matched budgets
- The final recommendation is stated in incremental contribution-margin terms with uncertainty
- The marketplace extension demonstrates capacity, spillover, and interference awareness
- The rollout plan contains explicit ramp, holdout, monitoring, and rollback rules
- Every phase contains a chart and a business-readable takeaway
- All experimental, estimated, and simulated results are labeled honestly
- The project can survive a ten-minute methodology deep dive and a ten-minute executive presentation

## Intended resume positioning

The project should support a bullet shaped like the following, populated only with verified project results:

```text
Built an end-to-end incentive allocation system using randomized experiment
analysis, heterogeneous treatment-effect modeling, and constrained optimization;
improved estimated incremental contribution margin by [X%] versus [baseline]
at a matched [budget/contact] constraint, with bootstrap uncertainty and a
capacity-aware marketplace rollout design.
```

Do not insert a percentage until the held-out policy evaluation is complete. Describe the result as estimated or simulated unless it was measured in a real deployment.

## Notes for coding agents

- Work phase by phase and do not jump to uplift modeling before validating the experiment and data contract
- Read the project charter and metric definition before changing modeling code
- Keep notebooks thin and reusable logic tested in `src/`
- Prefer a simple correct baseline over an impressive but opaque method
- Validate causal estimators on simulated known ground truth before applying them to Criteo
- Treat Criteo as randomized advertising data, not customer churn data
- Keep the marketplace extension and dashboard subordinate to the core decision narrative
- Flag weak overlap, unstable uplift, invalid uncertainty, or a policy that fails to beat simple baselines
- Preserve negative or inconclusive findings; do not tune the analysis solely to manufacture a positive resume metric
- Commit after each completed phase with tests passing
