# Learn & Build — Incentive Allocation & Budget-Constrained Decision Engine

**Companion to:** `increment_decision_engine_project_plan.md` (the build spec) and `project.md` (the architecture + interview doc).
**Purpose:** the exact things to learn, in the exact order you need them, and the exact thing you build the moment you learn them.
**Timeline:** 12 weeks at 15–20 focused hours/week. A 10-week compression is described at the end.

---

## 0. Rules of engagement

Read these once. They are the difference between a portfolio project and a pile of notebooks.

1. **Learn just-in-time, never just-in-case.** You do not learn causal inference in week 1. You learn it in week 6, the week you need it, and you immediately write code with it. Anything you learn more than 7 days before you use it, you will forget.
2. **One primary resource per topic.** Not three. If the primary resource doesn't land after one honest attempt, switch — don't stack.
3. **Every module ends in committed code.** A module is not "done" when you finish the video. It is done when a function exists in `src/`, a test passes, and a chart is saved to `reports/figures/`.
4. **Write the takeaway before the code.** One sentence, business language, no model names. If you can't write it, you don't understand what you're building.
5. **Time-box hard.** Each module has a budget. Blowing the budget by 2x means you're rabbit-holing. Ship the naive version and move on; you can come back in week 11.
6. **Interview prep runs in parallel from week 1**, not after. Roughly 3 hours/week. See Part 4.
7. **Preserve negative results.** If the uplift model doesn't beat treat-all, that is a finding and it is *more* impressive to discuss than a fabricated win. See `project.md` §Failure Modes.

**On the links below.** Every URL was checked in September 2026. Where I give a channel or a paper title instead of a deep link, that is deliberate — video IDs rot and I would rather give you an exact searchable title than a dead link. Search the exact quoted title; you'll land on it.

---

## 1. The 12-week map

| Wk | Learning module | Project phase (build) | Interview track |
|---|---|---|---|
| 1 | M0 Product framing & metric trees · M1 Unit economics | Phase 0 charter + metric tree | Product sense: metric definition |
| 2 | M2 Data modeling & synthetic generation · M3 SQL analytics | Phase 1 marketplace tables, funnels, cohorts | SQL: joins, grain, aggregation |
| 3 | M3 cont. (windows, PIT) · M4 Data contracts | Phase 2 SQL layer + tests | SQL: window functions, cohorts |
| 4 | M5 Probability & inference core | Phase 3a Criteo ITT analysis | Stats: CI, p-values, variance |
| 5 | M6 Experiment design (power, SRM, CUPED) | Phase 3b readout + power + multi-arm design | A/B test case questions |
| 6 | M7 Supervised ML for tabular + calibration | Phase 4 propensity baseline | ML: overfitting, leakage, metrics |
| 7 | M8 Causal inference foundations | Phase 5 estimator validation on ground truth | Causal: confounding, DAGs |
| 8 | M9 Heterogeneous treatment effects | Phase 6a T-learner, X-learner | Case: who to target |
| 9 | M10 Uplift evaluation & policy value | Phase 6b DR-learner, Qini, policy value | Case: how do you know it works |
| 10 | M11 Constrained optimization | Phase 7 ILP allocator + profit curve | Guesstimates + optimization framing |
| 11 | M12 Interference & marketplace experiments · M13 Rollout & monitoring | Phase 8 + Phase 9 | Marketplace case questions |
| 12 | M14 Communication & packaging | Phase 10 packaging | Full mock loops |

**Non-negotiable checkpoints.** End of week 3: a rebuildable, tested analytical table. End of week 5: a defensible ATE with an interval. End of week 9: a policy-value number with uncertainty. End of week 10: a profit-vs-budget curve. Miss one of these and you cut scope somewhere else, not from these four.

---

## PART 2 — LEARNING MODULES

---

### M0 · Product framing, metric trees, and the decision statement
**Time-box:** 6 hours · **Week 1** · **Unlocks:** Phase 0

**What you actually need**
- The difference between a *goal metric*, a *driver metric*, a *guardrail*, and a *diagnostic*.
- Metric anatomy: numerator, denominator, grain, time window, filter. Every metric you define must have all five written down.
- Why the denominator choice ("per eligible customer" vs "per treated customer") silently determines your conclusion.
- Guardrails as a harm hypothesis, not a checklist: what would this campaign break if it worked too well?
- The one-paragraph decision statement: who decides, what they choose between, what evidence flips the choice.

**Resources**
- **Read (primary):** Emily Riederer, *Column Names as Contracts* — https://dev.to/emilyriederer/column-names-as-contracts-4la6. Read it for the mindset: a data artifact is a promise to a consumer. You will apply this to metrics and to your schema.
- **Read:** Kohavi, Tang & Xu, *Trustworthy Online Controlled Experiments*, Ch. 6 ("Choosing Metrics") and Ch. 7 ("Metrics for Experimentation and the OEC") — https://www.cambridge.org/core/books/trustworthy-online-controlled-experiments/D97B26382EB0EB2DC2019A7A7B518F59. If you buy one book for this project, buy this one. Chapters 1–7 and 18–22 are the ones you'll use.
- **Watch:** Search *"Lenny's Podcast Ronny Kohavi A/B testing"* on YouTube. ~90 min. Watch for how a practitioner talks about OEC, guardrails, and why most ideas fail.
- **Read (fast):** Amplitude's *North Star Playbook* (amplitude.com — search "North Star Playbook"). Skim only Part 1–2 for the metric-tree vocabulary that PMs actually use.

**Checkpoint** — you can do all three without notes:
- State the decision in one paragraph without using the words model, ML, or algorithm.
- Draw the metric tree from incremental contribution margin down to two levels of drivers.
- Name three guardrails and explain the *mechanism* by which the campaign could break each one.

**Build**
- `docs/project_charter.md`, `docs/metric_definition.md`
- Metric tree figure → `reports/figures/metric_tree.png`
- `docs/assumptions_register.md` with margin %, redemption rate, interference, delayed outcomes — each with a value, a source, and a sensitivity range.

---

### M1 · Unit economics and the cost model
**Time-box:** 4 hours · **Week 1** · **Unlocks:** Phase 0, Phase 7

**What you actually need**
- Contribution margin = revenue − variable cost. What is variable in a delivery/e-commerce marketplace (COGS, payment fees, courier pay, support cost) and what is not (fixed platform cost). Fixed costs never enter an incremental decision.
- Offer cost accounting: **exposure cost** (you showed the offer) vs **redemption cost** (they used it). These differ by an order of magnitude and the choice changes your ROI by more than any modeling decision you will make.
- Cost per incremental order (CPIO) and why it is not cost per order.
- Cannibalisation: paying for orders that would have happened anyway. This is the single sentence that justifies the entire project.

**Resources**
- **Read:** Uber Engineering, *Beyond Prediction: Solving the Multiple Knapsack Problem at Scale* — https://www.uber.com/at/en/blog/solving-multiple-knapsack/. This is the closest public description of the exact system you are building. Read it now for vocabulary, and again in week 10 for the optimization.
- **Read:** *Practical Marketplace Optimization at Uber Using Causally-Informed Machine Learning* — https://arxiv.org/abs/2407.19078. Read §1–3 only. This is your citation for "why budget allocation is a real problem at real companies."
- **Do:** Build the unit-economics arithmetic yourself in a scratch notebook before you model anything. Take an order of ₹500, assume 22% contribution margin, a ₹75 offer, 60% redemption, and a 3pp incremental conversion lift. Compute CPIO and ROI. Do it by hand. Get the intuition that incremental economics are brutal.

**Checkpoint**
- You can explain, in 30 seconds, why a campaign with a 40% conversion rate in the treated group can still destroy value.
- You can write `value(i, a)` from the spec and defend each of its three terms.

**Build**
- `configs/base.yaml`: margin rate, offer values, redemption rates, cost accounting mode (`exposure` | `redemption`), all as named parameters. Never hard-code an economic assumption in a notebook.

---

### M2 · Data modeling and realistic synthetic generation
**Time-box:** 8 hours · **Week 2** · **Unlocks:** Phase 1

**What you actually need**
- Grain and primary key for every table. Say it out loud for each: "one row per ___".
- Event tables vs entity tables vs snapshot tables.
- Slowly changing state (user lifecycle) and why you need `valid_from` / `valid_to` or an event log you can replay.
- How to generate synthetic data that has *structure worth finding*: correlated features, heterogeneous response, seasonality, and a couple of realistic data-quality warts (duplicate events, a few impossible timestamps) so your Phase 2 tests have something to catch.
- Why you must be able to write down the true data-generating process. In Phase 5 you will need known ground truth.

**Resources**
- **Read:** DuckDB documentation, "Data Import" and "SQL Introduction" — https://duckdb.org/docs/. You need maybe 45 minutes here.
- **Read:** Kimball dimensional modeling basics. Search *"Kimball fact table grain declaration"*. You need the concept of declaring grain, not the whole book.
- **Reference:** NumPy `default_rng` docs — https://numpy.org/doc/stable/reference/random/generator.html. Every generator function takes a seed. Every one.

**Checkpoint**
- For each of your 9 tables you can state the grain, the PK, and which columns are known *before* the decision timestamp.
- You can regenerate the whole dataset deterministically from a seed in one command.

**Build**
- `src/data/generate_marketplace.py` — one function per table, each seeded, each returning a typed DataFrame. Include: `users`, `sessions`, `merchants`, `orders`, `offers`, `exposures`, `redemptions`, `cancellations`, `refunds`, `experiment_assignments`, `city_hour_capacity`.
- `sql/schema.sql` + `docs/data_dictionary.md` with grain and PK per table.
- Deliberately inject: 0.3% duplicate assignments, a handful of orders with `order_ts < signup_ts`, some negative-margin orders. Document that you injected them.

---

### M3 · SQL for analytics: funnels, cohorts, windows, point-in-time
**Time-box:** 14 hours across weeks 2–3 · **Unlocks:** Phase 1, Phase 2 · **Also your highest-leverage interview skill**

**What you actually need, in this order**
1. `GROUP BY` with correct grain; the fan-out trap (a join that multiplies rows and silently inflates every metric).
2. `LEFT JOIN` vs `INNER JOIN` semantics with null-producing sides; anti-joins via `NOT EXISTS`.
3. CTEs for readability; when a CTE is a materialisation boundary.
4. Funnel queries: sessions → cart → checkout → order, with the drop-off at each step, on one row per step.
5. Cohort retention: cohort by signup week, activity by week offset, pivoted into a triangle.
6. **Window functions** — `ROW_NUMBER`, `RANK`, `LAG`, `LEAD`, `SUM() OVER (PARTITION BY ... ORDER BY ... ROWS BETWEEN ...)`. Rolling 30/60/90-day RFM features live here.
7. **Point-in-time correctness** — the single most interview-relevant idea in this module. Every feature for user *i* must be computed using only events with `event_ts < decision_ts(i)`. The standard implementation is an as-of join: for each (user, decision_ts) row, aggregate the event table with a `<` predicate, not a `<=` on the date.
8. Set-based data-quality assertions: duplicate keys, orphan foreign keys, monotonic timestamps, row-count invariance across joins.

**Resources**
- **Read (primary, window functions):** PostgreSQL Tutorial — Window Functions — https://www.postgresql.org/docs/current/tutorial-window.html. Short, precise, and DuckDB follows Postgres semantics closely.
- **Reference:** DuckDB SQL docs — https://duckdb.org/docs/. Look specifically for `QUALIFY`, `ASOF JOIN`, and `USING SAMPLE`. `ASOF JOIN` is how you implement point-in-time joins cleanly and it is a genuinely good thing to show in a repo.
- **Practice (do this daily, 30 min):** https://datalemur.com/ — do every window-function and every "hard" question. Then https://www.stratascratch.com/ for the FAANG-tagged ones.
- **Watch:** YouTube channel *Ankit Bansal* — search *"SQL interview questions window functions Ankit Bansal"*. Best free explanations of the gnarly interview patterns (nth highest, gaps and islands, running totals with resets).
- **Read for the mindset:** Emily Riederer's column-name contracts piece (linked in M0) applied to your `sql/` layer.

**Checkpoint** — write these from scratch in under 15 minutes each:
- Weekly retention triangle from a signup table and an orders table.
- Rolling 30-day order count and margin per user, as of an arbitrary timestamp column, using a window frame.
- A query that proves a join did not fan out (`COUNT(*)` before vs after, plus a `HAVING COUNT(*) > 1` duplicate check on the join key).
- An as-of feature join that would break if you used `<=` instead of `<`.

**Build**
- `sql/product_metrics.sql`, `sql/retention_cohorts.sql`, `sql/user_features.sql`, `sql/experiment_metrics.sql`
- `src/data/build_features.py` — one command rebuilds `data/processed/eligible_users.parquet`, one row per eligible user at their decision timestamp.
- A **leakage test**: assert that no feature column's underlying source event has `event_ts >= decision_ts`. Write it as a failing test first, then fix the query.

---

### M4 · Data contracts and testing
**Time-box:** 4 hours · **Week 3** · **Unlocks:** Phase 2 gate

**What you actually need**
- Schema contracts: dtype, nullability, range, uniqueness, referential integrity.
- Business-rule contracts: `refund_amount <= order_amount`, bounded economic rates, and the synthetic decision-arm enum (`no_offer`, `small_offer`, `large_offer`). The Criteo source remains binary and is validated separately when M5 begins.
- Fixture-based unit tests for transformation logic: build a 12-row hand-written input where you know the right answer, and assert the exact output.
- Fail loud, fail at build time, not in the notebook three weeks later.

**Resources**
- **Docs:** Pandera — https://pandera.readthedocs.io/. Read "Dataframe Schemas" and "Checks". 45 minutes is enough.
- **Docs:** pytest fixtures — https://docs.pytest.org/en/stable/how-to/fixtures.html.

**Checkpoint** — `pytest` runs green, and if you deliberately corrupt one row in the generator, exactly one named test fails with a readable message.

**Build**
- `src/data/validate_data.py` — executable contracts for each raw table and the processed modeling table.
- `tests/test_features.py` plus the hand-built fixture module — exact fixture tests for the funnel, retention cohort, and PIT join.
- A `make build` / `make test` (or `invoke` / shell script) so the Phase 2 gate — "rebuild from raw with one command" — is literally true.

---

### M5 · Probability and inference core
**Time-box:** 10 hours · **Week 4** · **Unlocks:** Phase 3

**What you actually need** (and nothing more)
- Random variables, expectation, variance; variance of a sum; why variance of a proportion is `p(1-p)/n`.
- Sampling distribution vs population distribution vs data distribution. Most people confuse these in interviews.
- CLT and when it fails you: heavy-tailed revenue metrics, tiny base rates (Criteo conversion is ~0.29%), and ratio metrics.
- Standard error, confidence interval, and the correct verbal interpretation of both.
- p-value: what it is, what it is not, and why "not significant" ≠ "no effect".
- Type I / Type II error, and why the business cost of the two is asymmetric here.
- **Bootstrap** — percentile and BCa. This is your workhorse for uncertainty on Qini, on policy value, and on any quantity with no closed form. Learn the *unit* of resampling: you resample users, not rows of a merged table.
- **Delta method** for ratio metrics (e.g. margin per eligible user, CPIO). Know it exists and know when the naive SE is wrong.

**Resources**
- **Watch (primary):** StatQuest with Josh Starmer — https://www.youtube.com/@statquest — playlist *"Statistics Fundamentals"*. Watch: sampling distributions, standard error, confidence intervals, p-values (all three p-value videos), power. Skip the ML videos here; you get those in M7.
- **Watch:** 3Blue1Brown — https://www.youtube.com/@3blue1brown — *"Binomial distributions | Probabilities of probabilities"* and the Bayes videos, for intuition on small base rates.
- **Read:** *Trustworthy Online Controlled Experiments*, Ch. 17 ("The Statistics Behind Online Controlled Experiments") and Ch. 19 ("The A/A Test").
- **Read:** search *"delta method ratio metrics online experiments Deng Knoblich Lu"* — the standard industry reference for ratio-metric variance.
- **Do:** simulate. Write a loop that draws 10,000 A/A tests from your own synthetic data and confirms the false-positive rate is ~5%. Nothing teaches p-values faster.

**Checkpoint**
- You can derive the SE of a difference in proportions on paper.
- You can explain why bootstrapping rows of an order-level table gives you the wrong interval for a user-level metric.
- Your A/A simulation produces a uniform p-value histogram. If it doesn't, your analysis code has a bug — find it now, not in week 9.

**Build**
- `src/experimentation/estimation.py` — `diff_in_means()`, `bootstrap_ci()` (unit-aware), `delta_method_ratio_se()`.
- `reports/figures/aa_test_pvalue_histogram.png` — this single chart is a credibility signal in a portfolio.

---

### M6 · Experiment design: power, SRM, variance reduction, multi-arm
**Time-box:** 10 hours · **Week 5** · **Unlocks:** Phase 3

**What you actually need**
- Randomization unit vs analysis unit. Mismatch is the most common real-world experiment bug.
- **SRM (sample ratio mismatch)** — chi-square test on assignment counts against the designed ratio. If SRM fires, you stop analysing. Full stop. Know the common causes: bot filtering, redirect loss, logging asymmetry, triggering-condition bugs.
- Pre-treatment balance checks: how to run them, and why "imbalanced covariate → re-match the groups" is *wrong* on randomized data (you break the randomization you paid for).
- **Power and MDE.** `MDE ≈ (z_{α/2} + z_β) · sqrt(2σ²/n)`. Know how MDE scales with n (as 1/√n), and be able to say "to detect a 0.5pp lift on a 4.7% base rate at 80% power I need roughly N users per arm" with an actual number.
- **Variance reduction:** CUPED / regression adjustment with pre-period covariates. Critically: on randomized data this improves *precision*, it does not fix bias, and it must be pre-specified.
- Multiple testing across metrics and segments; pre-specifying a small segment list.
- Multi-arm design: allocation across control / small offer / large offer, and the power cost of splitting traffic.
- Novelty effects, primacy effects, and the winner's curse (why the first significant result is biased upward).

**Resources**
- **Read (primary):** *Trustworthy Online Controlled Experiments*, Ch. 3 (Twyman's Law and trustworthiness), Ch. 15 (SRM/A-A), Ch. 18 (variance reduction), Ch. 22 (guardrails). This module *is* that book.
- **Read (free, 20 min):** Kohavi, *Trustworthy A/B Tests: Pitfalls in Online Controlled Experiments* — https://exp-platform.com/Documents/2017-05-17EmetricsControlledExperimentsPitfallsKohaviNR.pdf. Slides, dense, extremely quotable in interviews.
- **Read:** Fabijan et al., *"Diagnosing sample ratio mismatch in online controlled experiments: a taxonomy and rules of thumb for practitioners"* (KDD 2019). Search the exact title. The taxonomy of SRM causes is a great interview answer.
- **Read:** search *"CUPED Deng Xu Kohavi Walker Improving the sensitivity of online controlled experiments"* (WSDM 2013).
- **Docs:** `statsmodels.stats.power` — https://www.statsmodels.org/stable/stats.html#power-and-sample-size-calculations.

**Checkpoint**
- Given treatment/control counts, you compute the SRM p-value in your head-adjacent way (chi-square, 1 df) and state the stop/go rule.
- You can compute MDE for your Criteo sample and for a hypothetical 4-week marketplace test, and explain the trade-off of adding a third arm.
- You can explain in one sentence why regression adjustment is allowed here but propensity matching is not.

**Build**
- `src/experimentation/diagnostics.py` — `srm_test()`, `balance_table()` (standardized mean differences, with a note that you are *reporting* not *correcting*).
- `src/experimentation/power.py` — `mde()`, `required_n()`, and a power curve figure.
- `docs/experiment_design.md` — the pre-registered multi-arm design: hypotheses, primary metric, MDE, duration, allocation, guardrails, stopping rules, and the decision matrix (what result → what action).

---

### M7 · Supervised ML for tabular data, calibration, and leakage
**Time-box:** 10 hours · **Week 6** · **Unlocks:** Phase 4 (and the base learners for Phase 6)

**What you actually need**
- Logistic regression as the baseline you must beat, and why a calibrated logistic model is often enough.
- Gradient boosting (LightGBM): what the trees do, what `num_leaves`, `min_data_in_leaf`, `learning_rate`, and early stopping actually control. You do not need the math of GOSS/EFB.
- Train/validation/test discipline. Temporal splitting for longitudinal data; stratification for rare outcomes.
- **Leakage taxonomy** — target leakage (post-treatment features), train-test contamination (fitting the scaler before the split), group leakage (same user in train and test), temporal leakage (future information). Be able to name all four.
- Metrics: ROC-AUC vs PR-AUC (and why PR-AUC matters at a 0.29% base rate), log loss, Brier score.
- **Calibration** — Platt scaling and isotonic regression, reliability diagrams. This is not optional here: you multiply predicted probabilities by rupees. An uncalibrated model produces confidently wrong money.
- The core conceptual line of the whole project: `P(Y=1|X)` is not `E[Y(1) − Y(0)|X]`.

**Resources**
- **Watch (primary):** StatQuest — https://www.youtube.com/@statquest — playlist *"Machine Learning"* (https://www.youtube.com/playlist?list=PLblh5JKOoLUICTaGLRoHQDuF_7q2GfuJF). Watch: bias/variance, cross-validation, ROC & AUC, logistic regression, decision trees, gradient boost parts 1–2. Skip the rest.
- **Docs (primary for calibration):** scikit-learn, *Probability calibration* — https://scikit-learn.org/stable/modules/calibration.html. Read it properly, including the caveat about calibrating on held-out data.
- **Docs:** LightGBM parameter tuning — https://lightgbm.readthedocs.io/en/stable/Parameters-Tuning.html.
- **Read:** search *"Kaufman Rosset Perlich Leakage in Data Mining: Formulation, Detection, and Avoidance"*. The canonical leakage paper; the fishing-tackle example is a great interview story.

**Checkpoint**
- You can produce a reliability diagram and explain what a curve bowing below the diagonal means in money.
- You can list four kinds of leakage and point to where each could occur *in your own pipeline*.
- You can explain to a PM why "the model is 0.82 AUC" says nothing about whether to send the offer.

**Build**
- `src/prediction/propensity.py` — calibrated logistic baseline + LightGBM comparator, with `CalibratedClassifierCV` on a held-out fold.
- `reports/figures/calibration_curve.png`, `reports/figures/lift_curve.png`.
- `docs/why_propensity_is_not_uplift.md` — one page. This document does disproportionate interview work. Include the 2x2: high propensity/high uplift, high propensity/low uplift (sure things — you're burning budget), low propensity/high uplift (persuadables), low/low (lost causes).

---

### M8 · Causal inference foundations
**Time-box:** 14 hours · **Week 7** · **Unlocks:** Phase 5 · **This is the module that separates you from other candidates**

**What you actually need**
- **Potential outcomes** `Y(1), Y(0)`; the fundamental problem of causal inference; ATE, ATT, CATE. Be fluent in this notation — you will write it on a whiteboard.
- Identification assumptions: **unconfoundedness (ignorability), positivity/overlap, SUTVA, consistency.** For each, know: what it means, what breaks if it fails, how you'd check it, and whether randomization gives it to you for free.
- **DAGs**: confounder, mediator, collider. Back-door criterion. Why controlling for a collider *creates* bias and why controlling for a mediator answers a different question. Why you must never include post-treatment variables.
- Estimators, in escalating order: naive difference in means → regression adjustment → IPW (inverse propensity weighting) → **AIPW / doubly robust**. Understand *why* DR is called doubly robust (consistent if either the outcome model or the propensity model is right).
- Overlap diagnostics: propensity histograms by arm, trimming, and what extreme weights do to your variance.
- What randomization buys you: it makes the propensity known and constant, which is why on Criteo you do *not* need matching, and why claiming you do is a red flag.

**Resources**
- **Watch (primary):** Brady Neal, *Introduction to Causal Inference* — course page https://www.bradyneal.com/causal-inference-course, lecture playlist https://www.youtube.com/playlist?list=PLoazKTcS0Rzb6bb9L508cyJ1z-U9iWkA0. Watch chapters 1–4 (potential outcomes, graphical models, back-door, estimation). Start with the 20-min preview: https://www.youtube.com/watch?v=DXBPtpBhGqo. Budget ~6 hours. This is the best free treatment for an ML audience.
- **Read (primary, code):** Matheus Facure, *Causal Inference for the Brave and True* — https://matheusfacure.github.io/python-causality-handbook/landing-page.html. Part I chapters 1–5, 10 (propensity score), 12 (doubly robust). Code you can run and steal patterns from.
- **Reference:** Nick Huntington-Klein, *The Effect* — https://theeffectbook.net/. Chapters 5–8 for DAGs, explained better than anywhere else. Free online.
- **Reference (rigour, dip in only):** Hernán & Robins, *Causal Inference: What If* — https://www.hsph.harvard.edu/miguel-hernan/causal-inference-book/. Free PDF. Use Part I Ch. 1–3 as a definitions check.
- **Optional:** Cunningham, *Causal Inference: The Mixtape* — https://mixtape.scunning.com/. Better if you like an econometrics framing.

**Checkpoint**
- You can draw the DAG for your own project and mark which variables you include and which you exclude, with reasons.
- You can state all four identification assumptions and say which ones randomization gives you and which it does not (SUTVA it does *not* — remember this for Phase 8).
- You can implement IPW and AIPW from scratch in ~30 lines each, and explain when the weights blow up.

**Build**
- `src/causal/simulate.py` — four DGPs: constant effect, heterogeneous effect, confounded assignment, poor overlap. Known ground truth in every case.
- `src/causal/estimators.py` — `naive_diff()`, `regression_adjust()`, `ipw()`, `aipw()`.
- `src/causal/evaluation.py` — repeated-simulation bias and 95% interval coverage across estimators.
- `reports/figures/estimator_recovery.png`, `reports/figures/overlap_diagnostics.png`, `docs/dag.png`.
- **The money experiment:** take the randomized Criteo data, deliberately construct a biased observational subsample (drop treated users with low `f0` at a higher rate), estimate the effect observationally, and show how far off it is from the randomized benchmark — then show DR recovering some of it. That comparison chart is worth more in an interview than any model you build.

---

### M9 · Heterogeneous treatment effects (uplift modeling)
**Time-box:** 12 hours · **Week 8** · **Unlocks:** Phase 6a

**What you actually need**
- CATE `τ(x) = E[Y(1) − Y(0) | X = x]` and why it is fundamentally harder than prediction: you never observe the label.
- The meta-learner ladder and the bias/variance trade-off of each:
  - **S-learner** — one model with `T` as a feature. Cheap. Regularization can shrink the treatment effect to zero if `T` is one weak feature among many.
  - **T-learner** — two models. No shrinkage of the effect, but you difference two independently-noisy models, and it splits your data.
  - **X-learner** — imputes individual effects, then models them; propensity-weighted combination. Designed for imbalanced arms. Criteo is 85/15 treated, so this is genuinely the right tool, and saying *why* is a strong signal.
  - **DR-learner** — builds a doubly robust pseudo-outcome, then regresses it on `X`. Needs cross-fitting. This is the one to make your final candidate.
  - **R-learner** and **causal forest** — know what they are, know they exist, only implement if week 8 goes fast.
- **Cross-fitting**: fit nuisance models on fold −k, predict on fold k. Without it, your pseudo-outcomes are overfit and your CATE is garbage in a way that no metric will loudly tell you.
- Modeled latent segments: persuadables / sure things / lost causes / sleeping dogs. These are *outputs of a model*, not observed customer types. Never present them as facts.
- Why uplift is a low signal-to-noise problem, and why a flat uplift curve is a legitimate and publishable finding.

**Resources**
- **Read (primary, conceptual):** Facure, Ch. 18 *Heterogeneous Treatment Effects and Personalization* — https://matheusfacure.github.io/python-causality-handbook/18-Heterogeneous-Treatment-Effects-and-Personalization.html, and Ch. 21 *Meta Learners* — https://matheusfacure.github.io/python-causality-handbook/21-Meta-Learners.html.
- **Read (primary, precise):** EconML user guide, *Meta-Learners* — https://www.pywhy.org/EconML/spec/estimation/metalearners.html. Short, exact formulas for S/T/X/DA/DR learners.
- **Run:** EconML metalearners notebook — https://github.com/py-why/EconML/blob/main/notebooks/Metalearners%20Examples.ipynb. Run it end to end before writing your own.
- **Papers (read the abstract + method section only):**
  - Künzel, Sekhon, Bickel & Yu, *"Metalearners for estimating heterogeneous treatment effects using machine learning"* (PNAS 2019) — the X-learner.
  - Kennedy, *"Towards optimal doubly robust estimation of heterogeneous causal effects"* — the DR-learner.
  - Nie & Wager, *"Quasi-Oracle Estimation of Heterogeneous Treatment Effects"* — the R-learner.
- **Libraries:** `causalml` (Uber) — https://github.com/uber/causalml · `scikit-uplift` — https://github.com/maks-sh/scikit-uplift, docs at https://www.uplift-modeling.com/. Use `scikit-uplift` for the metrics and plots; write your own learners so you can explain every line.
- **Read (critical thinking):** Facure Ch. 23 *Challenges with Effect Heterogeneity and Nonlinearity* — https://matheusfacure.github.io/python-causality-handbook/23-Challenges-with-Effect-Heterogeneity-and-Nonlinearity.html. This chapter will save you from a wrong conclusion.

**Checkpoint**
- You can implement T-learner and X-learner from scratch and explain, without notes, why X-learner helps under 85/15 imbalance.
- You can explain what cross-fitting protects against and what happens without it.
- You never say "this customer is a persuadable." You say "the model places this customer in the top decile of estimated uplift."

**Build**
- `src/causal/meta_learners.py` (`ConstantEffect`, `SLearner`, `TLearner`, `XLearner`), `src/causal/dr_learner.py` with explicit K-fold cross-fitting.
- Validate every learner against your M8 simulator first: on the known-heterogeneous DGP, the learner's τ̂ should correlate with true τ. If it doesn't, the bug is yours, not the data's.

---

### M10 · Uplift evaluation and policy value
**Time-box:** 10 hours · **Week 9** · **Unlocks:** Phase 6b, Phase 7 · **Most candidates skip this. Don't.**

**What you actually need**
- Why you cannot use AUC, RMSE, or any prediction metric: the target is unobserved. Anyone who reports "uplift model AUC" has misunderstood the problem.
- **Uplift by decile** — rank by τ̂, then within each decile compute the *actual* treated-minus-control difference. Monotone decreasing is what you want to see. This is the chart a PM understands.
- **Qini curve and Qini coefficient**; **cumulative gain / AUUC**. Know the difference (Qini weights by treated count; AUUC uses the average uplift scaled by population) and know that the random baseline for a normalized AUUC is ~0.5 while the Qini null is ~0.
- **Policy value** — the number that actually matters. Given a policy π(x) ∈ {actions}, estimate `E[Y(π(X))]` on held-out randomized data. Two estimators:
  - *IPW / direct randomized*: since assignment is random with known propensity, average the outcomes of units whose actual treatment matched what π would have chosen, reweighted. Unbiased, higher variance.
  - *Doubly robust (AIPW) policy value*: combines an outcome model with the IPW correction. Lower variance, still consistent if one part is right. Use this as primary.
- **Bootstrap uncertainty on curves and on policy value.** Resample users, recompute the full pipeline's evaluation (not the model fit — be explicit about which you're doing and why), report a band.
- Stability checks: across seeds, across pre-treatment segments, across time slices.

**Resources**
- **Read (primary):** Facure, Ch. 19 *Evaluating Causal Models* — https://matheusfacure.github.io/python-causality-handbook/19-Evaluating-Causal-Models.html, then Ch. 20 *Plug-and-Play Estimators* — https://matheusfacure.github.io/python-causality-handbook/20-Plug-and-Play-Estimators.html. Chapter 19 is the single most valuable chapter in this project.
- **Docs + source:** `scikit-uplift` metrics — https://www.uplift-modeling.com/ (`qini_auc_score`, `uplift_auc_score`, `uplift_at_k`, `plot_qini_curve`). Read the implementation in `sklift/metrics/metrics.py`; it's short and it teaches you what the curves actually are.
- **Read:** Devriendt, Guns & Verbeke, *"Learning to rank for uplift modeling"* — for the evaluation-metric discussion.
- **Read:** Athey & Wager, *"Efficient Policy Learning"* — abstract and §2 only, for the policy-value framing and the vocabulary of regret.
- **Read:** Diemert et al., *"A Large Scale Benchmark for Uplift Modeling"* (AdKDD 2018) via https://ailab.criteo.com/criteo-uplift-prediction-dataset/ — the dataset paper. Read it because you must document your data source properly.

**Checkpoint**
- You can explain the Qini curve to a non-technical person in three sentences using the axes.
- You can state your policy value with a bootstrap interval and say what "the interval crosses treat-all" would mean for the recommendation.
- You have an honest answer to "how do you know your uplift model isn't just noise?" — the answer is a random-ranking null baseline, run and charted.

**Build**
- `src/causal/evaluation.py` — `uplift_by_decile()`, `qini_curve()`, `auuc()`, `policy_value_ipw()`, `policy_value_dr()`, `bootstrap_policy_value()`.
- **Mandatory null baseline:** score a uniform-random ranking through the exact same evaluation and plot it alongside. If your model's Qini interval overlaps the noise ranking's, say so out loud in `docs/model_card.md`.
- `docs/model_card.md` — intended use, training data, features (with the pre-treatment proof), metrics with intervals, known failure modes, out-of-scope uses.

---

### M11 · Constrained optimization
**Time-box:** 12 hours · **Week 10** · **Unlocks:** Phase 7

**What you actually need**
- **LP formulation discipline**: decision variables, objective, constraints, and then — separately — whether the problem is integral.
- The **0/1 knapsack** and the **multiple-choice knapsack (MCKP)**. Your problem is MCKP: for each customer choose *exactly one* of {no_offer, small, large}, subject to a shared budget. Recognising this and naming it is a strong interview moment.
- The **greedy ratio heuristic**: sort by (incremental value / incremental cost), take until budget exhausted. For a pure single-budget knapsack with many small items, this is near-optimal. You should implement it, because the honest finding is often "the ILP beats greedy by 0.4%" and that is a *good* result to be able to discuss.
- **LP relaxation and the Lagrangian view**: relax the budget with multiplier λ, and the problem decomposes per customer into "treat if value − λ·cost > 0". λ is the **shadow price of budget** — the marginal contribution margin per extra rupee. This one object gives you: the profit-vs-budget curve, the "how much more budget should we ask for" answer, and a scalable serving strategy. It is the single best idea in Phase 7.
- **Integrality and when it matters**: with per-customer binary variables and one budget row, the LP relaxation has at most one fractional variable, so LP + rounding is essentially optimal. Adding segment constraints, frequency caps, and city-hour capacity is what makes ILP genuinely necessary.
- Solver mechanics: CBC vs SCIP vs CP-SAT; MIP gap; time limits; warm starts; what to do when 10 million binary variables doesn't fit (answer: Lagrangian decomposition, or bucket customers into cells and solve at cell level).

**Resources**
- **Docs (primary):** Google OR-Tools — https://developers.google.com/optimization. Work through the *Linear Programming* intro, the *Knapsack* guide, and the *CP-SAT* primer. Budget 4 hours.
- **Docs:** PuLP — https://coin-or.github.io/pulp/. Simpler API; good for your first formulation before you move to OR-Tools.
- **Read (primary industry reference):** Uber, *Beyond Prediction: Solving the Multiple Knapsack Problem at Scale* — https://www.uber.com/at/en/blog/solving-multiple-knapsack/. Uplift models + budget pacer + CP-SAT. This is your design north star.
- **Read (academic framing):** *End-to-End Cost-Effective Incentive Recommendation under Budget Constraint with Uplift Modeling* — https://arxiv.org/abs/2408.11623. Read §1–3 for the two-stage (estimate then allocate) framing and its criticisms — the criticism is a great answer to "what would you do next?".
- **Read:** Goldenberg, Albert, Bernardi & Estevez, *"Free Lunch! Retrospective Uplift Modeling for Dynamic Promotions Recommendation within ROI Constraints"* (RecSys 2020, Booking.com). Search the exact title.
- **Watch:** MIT OpenCourseWare 15.053 *Optimization Methods in Business Analytics* — search *"MIT 15.053 linear programming duality shadow price"*. You need the duality/shadow-price lecture, not the whole course.

**Checkpoint**
- You can write the MCKP formulation on a whiteboard: variables, objective, three constraint families.
- You can explain the shadow price of the budget constraint in business language: "the next ₹1 of budget buys ₹X of incremental margin, and here is where that falls below 1."
- You can say when greedy is enough and when it isn't.

**Build**
- `src/policy/value.py` — τ̂ → expected incremental contribution margin, with the cost model from M1.
- `src/policy/baselines.py` — treat-none, treat-all, random, propensity, uplift-rank, net-value-rank. All must accept the same budget and return the same object.
- `src/policy/optimize.py` — MCKP as ILP, plus a Lagrangian/threshold solver, plus greedy. Assert the three agree within tolerance on a small instance (this is your correctness test).
- `reports/figures/profit_vs_budget.png` — the headline chart of the whole project. Overlay all policies at matched budgets, with bootstrap bands.
- `reports/figures/shadow_price_curve.png` — marginal margin per additional rupee.

---

### M12 · Interference, marketplaces, and geo experiments
**Time-box:** 8 hours · **Week 11** · **Unlocks:** Phase 8

**What you actually need**
- **SUTVA**, precisely: no interference between units, and one version of treatment. Randomization does *not* give you SUTVA. In a marketplace, treating user A consumes courier capacity that user B needed, so B's control outcome depends on A's assignment. Your user-level ATE is then biased, usually optimistically.
- Direction of the bias: with a shared, congested supply, individual-level A/B tests typically **overstate** the effect of a demand-stimulating treatment, because the control group absorbs the congestion externality.
- Design responses, and the trade-offs of each:
  - **Cluster / geo randomization** — randomize cities or regions. Unbiased-ish if clusters are near-independent; expensive in power because n drops from millions of users to dozens of cities.
  - **Switchback (time-region) randomization** — alternate treatment over time within a region. Handles simultaneous interference; carries carryover-effect risk and low power.
  - **Budget-split design** — split the *budget* rather than the users, so arms compete against themselves. Higher power than switchback; requires platform support.
- Short-run vs equilibrium effects: a promo that works when 1% of users get it may not work when 100% do, because supply and prices respond.
- Capacity as an optimization constraint, not just an experimental nuisance: incremental orders per city-hour ≤ available capacity.

**Resources**
- **Read (primary):** DoorDash, *Switchback Tests and Randomized Experimentation Under Network Effects* — https://careersatdoordash.com/blog/switchback-tests-and-randomized-experimentation-under-network-effects-at-doordash/.
- **Read:** DoorDash, *How DoorDash Ads keep consumers first with budget A/B experimentation* — https://careersatdoordash.com/blog/doordash-ads-uses-budget-a-b-experimentation/. Excellent explicit comparison of switchback vs cluster vs budget-split with reasons.
- **Read:** Liu, Mao & Kang, *Trustworthy and Powerful Online Marketplace Experimentation with Budget-split Design* — https://arxiv.org/abs/2012.08724. §1–3.
- **Read:** Li, Zhao, Johari & Weintraub, *"Interference, Bias, and Variance in Two-Sided Marketplace Experimentation: Guidance for Platforms"*. Search the exact title. The bias/variance framing of design choice is exactly what a marketplace-DS interviewer wants to hear.
- **Read:** *Trustworthy Online Controlled Experiments*, Ch. 22 (Leakage and Interference).

**Checkpoint**
- You can explain, with a concrete two-order example, how treating one user biases another user's control outcome.
- You can compare geo, switchback, and budget-split on bias, power, and implementation cost, and pick one for *your* project with a reason.

**Build**
- `src/marketplace/capacity.py` — city-hour incremental-order capacity constraint added to the optimizer.
- `src/marketplace/geo_experiment.py` — cluster assignment, cluster-robust SE, and MDE for a geo design at your simulated scale.
- `reports/figures/capacity_aware_vs_naive.png` — the chart showing an individually-profitable policy overloading a city-hour and destroying value through delivery-time and cancellation guardrails.
- `docs/geo_experiment_memo.md` — one page: design chosen, why, MDE, duration, what you'd do if power is insufficient.

---

### M13 · Rollout, monitoring, and realized impact
**Time-box:** 6 hours · **Week 11** · **Unlocks:** Phase 9

**What you actually need**
- Staged rollout with pre-committed gates (5% → 20% → 50% → 100%) and what evidence moves you between them.
- **Persistent holdout** — a permanent 1–2% never-treated group is how you measure realized incremental value forever, not just at launch. Know the cost: you give up value on those users, and you must be able to size that cost.
- Rollback thresholds on primary *and* guardrail metrics, defined before launch.
- Sequential testing / peeking: why repeatedly checking a fixed-horizon p-value inflates false positives, and the two standard fixes (alpha spending, always-valid confidence sequences). You don't have to implement one; you must know why naive peeking is wrong.
- **Delayed outcomes**: conversions land after the exposure. Incomplete outcome windows make early results look worse than they are. Either wait, or model the lag curve, and say which.
- Drift: feature drift (PSI / KS), calibration drift, policy drift (the *share of budget going to each segment* moving over time is the earliest warning sign and almost nobody monitors it).
- Retraining triggers: calibration degradation, drift threshold, holdout-measured lift decay, or a fixed cadence — pick and justify.
- Offline expected value vs online realized value; expect the online number to be smaller, and be ready to explain why (interference, drift, novelty, optimizer overfitting to noisy τ̂).

**Resources**
- **Read:** *Trustworthy Online Controlled Experiments*, Ch. 15 (ramping) and Ch. 20–21.
- **Read:** search *"Evidently AI data drift detection PSI KS"* for a concrete drift-metric reference — https://www.evidentlyai.com/ has readable guides.
- **Read:** search *"always valid inference confidence sequences Johari Koomen Pekelis Walsh"* for the peeking problem.

**Checkpoint** — a reader of your rollout doc can answer, without asking you: what ramps it, what pauses it, what rolls it back, what retrains it.

**Build**
- `src/monitoring/drift.py`, `src/monitoring/realized_value.py`
- `docs/rollout_plan.md` with a decision table (metric → threshold → action → owner).
- A simulated 8-week rollout in `app/dashboard.py`: budget utilisation, allocation mix by segment, realized vs expected margin, guardrails with alert thresholds.

---

### M14 · Communication, packaging, and the executive layer
**Time-box:** 8 hours · **Week 12** · **Unlocks:** Phase 10 · **This module has the highest interview ROI per hour**

**What you actually need**
- **Pyramid principle** (Minto): answer first, then three supporting arguments, then evidence. This is how MBB expects you to talk. Every section of your case study, every answer in an interview.
- **Situation → Complication → Question → Answer** for framing the problem.
- Chart discipline: one message per chart, the message in the title ("Optimized targeting delivers 1.6x the incremental margin of treat-all at the same ₹2M budget" — not "Profit vs budget").
- Labeling honesty: three tiers, visually distinguished everywhere — **measured** (from the RCT), **estimated** (model output on held-out data), **simulated** (synthetic marketplace). Mislabeling one of these is the fastest way to lose a technical interviewer.
- The three-length pitch: 30 seconds, 2 minutes, 10 minutes. Rehearse all three out loud.

**Resources**
- **Read:** Barbara Minto, *The Pyramid Principle* — you can get the operative ideas from a good summary; search *"Minto Pyramid Principle SCQA summary"*. Don't spend more than an hour.
- **Read:** Cole Nussbaumer Knaflic, *Storytelling with Data* — https://www.storytellingwithdata.com/. Skim the chapters on decluttering and on "so what".
- **Do:** record yourself giving the 10-minute version. Watch it. It will be bad. Do it again. This is the exercise, not the reading.

**Build**
- `README.md` — business decision and headline result in the first 15 lines, before any mention of Python.
- `docs/executive_case_study.pdf` — two pages, SCQA, situation → analysis → recommendation → impact → risks.
- `docs/technical_appendix.md` — estimators, assumptions, validation, limitations.
- `reports/experiment_readout.pdf`
- Ten-minute deck + rehearsed 30-second and 2-minute versions.

---

## PART 3 — EXACTLY WHAT TO BUILD

The original spec lists the phases. This section is the **artifact contract**: for each week, the specific files that must exist and the specific claim each one lets you make in an interview. If a file exists but you can't state its claim, the file is decoration — delete it.

### Week 1 — Framing
| Artifact | The claim it earns you |
|---|---|
| `docs/project_charter.md` | "I can state the decision, the decider, and the alternatives without mentioning a model." |
| `docs/metric_definition.md` | "Every metric here has a numerator, denominator, grain, window, and filter." |
| `docs/assumptions_register.md` | "Here are the six numbers my result depends on, and here's the range each could plausibly take." |
| `configs/base.yaml` | "No economic assumption is hard-coded anywhere in my analysis." |
| `reports/figures/metric_tree.png` | "This is how a ₹1 of promo budget is supposed to become ₹X of margin." |

### Weeks 2–3 — Data foundation
| Artifact | The claim |
|---|---|
| `src/data/generate_marketplace.py` | "Fully seeded; I can regenerate everything and I know the true DGP." |
| `sql/schema.sql` + `docs/data_dictionary.md` | "Grain and PK declared for all 11 tables." |
| `sql/*.sql` (5 files) | "Funnel, cohorts, RFM, exposure/outcome, and the eligible-user table are all SQL, not pandas." |
| `src/data/build_features.py` | "One command rebuilds the modeling table from raw." |
| `src/data/validate_data.py` + `tests/` | "The pipeline fails loudly on duplicate assignments, orphan keys, impossible values, and post-treatment leakage." |
| `reports/figures/funnel.png`, `retention_heatmap.png`, `lifecycle_segments.png` | "Here's where in the funnel and lifecycle an incentive could plausibly create value." |
| **The leakage test** | "Every feature is provably pre-treatment. Here's the test that would fail if it weren't." |

### Weeks 4–5 — Experiment
| Artifact | The claim |
|---|---|
| `src/experimentation/diagnostics.py` | "SRM checked before anything else. Balance reported, not corrected." |
| `src/experimentation/estimation.py` | "ITT with correct SEs, plus regression adjustment as a pre-specified precision comparison." |
| `src/experimentation/power.py` | "Here's the MDE I had, and the MDE I'd need for the multi-arm test." |
| `reports/figures/aa_test_pvalue_histogram.png` | "My inference code is calibrated. I tested it." |
| `reports/experiment_readout.pdf` | "Ship / don't ship, with uncertainty, effect size, guardrails, and validity all addressed." |
| `docs/experiment_design.md` | "Pre-registered multi-arm design with a decision matrix." |

### Week 6 — Deliberate strawman
| Artifact | The claim |
|---|---|
| `src/prediction/propensity.py` | "Calibrated, benchmarked against logistic regression, evaluated with PR-AUC because the base rate is 0.29%." |
| `reports/figures/calibration_curve.png` | "I multiply these probabilities by rupees, so I checked they mean what they say." |
| `docs/why_propensity_is_not_uplift.md` | "I built the naive targeting policy on purpose, so I could show exactly how much money it wastes on sure things." |

### Week 7 — Trust in the estimator
| Artifact | The claim |
|---|---|
| `src/causal/simulate.py` + `estimators.py` | "I validated my estimators against known ground truth before pointing them at real data." |
| `reports/figures/estimator_recovery.png` | "Bias and 95% coverage across 500 simulations, for four estimators, under four DGPs." |
| `reports/figures/overlap_diagnostics.png` | "Here's what my estimator does when positivity fails — it visibly breaks, which is the correct behaviour." |
| `reports/figures/obs_vs_rct.png` | "I induced confounding in randomized data and measured how wrong the observational estimate got." |
| `docs/dag.png` | "Here's my identification argument as a graph, including what I deliberately excluded." |

### Weeks 8–9 — Uplift
| Artifact | The claim |
|---|---|
| `src/causal/meta_learners.py`, `dr_learner.py` | "Constant-effect baseline, T, X, and a cross-fitted DR-learner. I can derive each." |
| `src/causal/evaluation.py` | "Uplift deciles, Qini, AUUC, and DR policy value — never AUC." |
| `reports/figures/qini_comparison.png` | "All learners plus a random-ranking null, with bootstrap bands." |
| `reports/figures/uplift_deciles.png` | "Actual treated-minus-control by predicted-uplift decile, on held-out randomized data." |
| `docs/model_card.md` | "Intended use, features, metrics with intervals, known failure modes, out-of-scope uses." |
| Stability table | "Across 5 seeds and 4 pre-treatment segments, the ranking holds / doesn't hold — here's which." |

### Week 10 — The decision engine
| Artifact | The claim |
|---|---|
| `src/policy/value.py` | "τ̂ → expected incremental contribution margin, with redemption-adjusted cost." |
| `src/policy/baselines.py` | "Six comparison policies, all evaluated at matched budgets." |
| `src/policy/optimize.py` | "MCKP as an ILP, cross-checked against a Lagrangian solver and greedy." |
| `reports/figures/profit_vs_budget.png` | **The headline.** "At a ₹X budget the optimized policy delivers Y% more incremental margin than treat-all, with a bootstrap band." |
| `reports/figures/shadow_price_curve.png` | "The marginal rupee of budget returns ₹λ. Below λ = 1, stop funding the campaign." |
| Allocation diagnostics | "Here's who gets which offer and why, and here's the segment mix at each budget level." |

### Week 11 — Marketplace + rollout
| Artifact | The claim |
|---|---|
| `src/marketplace/capacity.py` | "City-hour capacity is a constraint in the optimizer, not an afterthought." |
| `reports/figures/capacity_aware_vs_naive.png` | "Individually profitable targeting overloads three city-hours and turns net-positive into net-negative once delivery-time guardrails are priced in." |
| `src/marketplace/geo_experiment.py` + `docs/geo_experiment_memo.md` | "Here's why user-level randomization can't validate this, and here's the design that can, with its MDE." |
| `docs/rollout_plan.md` | "Ramp gates, persistent holdout, rollback thresholds, retraining triggers." |
| `src/monitoring/*` + `app/dashboard.py` | "Budget utilisation, allocation drift, calibration drift, realized vs expected margin." |

### Week 12 — Packaging
`README.md` (decision-first) · `docs/executive_case_study.pdf` (2 pages) · `docs/technical_appendix.md` · 10-minute deck · reproducible setup with a small example dataset · `v1.0` tag · every unused notebook and dependency deleted.

---

## PART 4 — PARALLEL INTERVIEW READINESS TRACK

3 hours/week, every week, from week 1. Non-negotiable. The project makes you *interesting*; this track makes you *hireable*.

### The weekly rhythm
- **90 min — SQL.** DataLemur or StrataScratch. Timed. Write the query before running it.
- **60 min — one case, out loud, recorded.** Alternate: product-sense case / experimentation case / MBB-style business case.
- **30 min — flashcards.** Definitions you must produce instantly: SUTVA, ignorability, positivity, ITT, CATE, Qini, CUPED, SRM, MDE, shadow price, doubly robust, collider, cross-fitting.

### Week-by-week focus
| Wk | SQL | Case | Concept drill |
|---|---|---|---|
| 1 | Joins, grain, aggregation | Define success for a promo feature | Metric anatomy, guardrails |
| 2 | Multi-table, anti-joins | Funnel drop-off diagnosis | Funnel & cohort definitions |
| 3 | Window functions, cohorts | "DAU dropped 8%, why?" | PIT correctness, leakage |
| 4 | Date logic, gaps & islands | Design an A/B test end to end | CI, p-value, power |
| 5 | Ratio metrics, self-joins | "Test is flat — what now?" | SRM, MDE, CUPED, novelty |
| 6 | Optimization & CTE refactoring | Model-vs-heuristic trade-off | Leakage, calibration, PR-AUC |
| 7 | Pivots, sessionisation | "Users who did X churn less — should we push X?" | Confounding, DAG, IPW, DR |
| 8 | Hard mixed sets | "Which users get the coupon?" | S/T/X/DR learners |
| 9 | Hard mixed sets | "How do you know targeting works?" | Qini, policy value, OPE |
| 10 | Timed mock (5 in 45 min) | Guesstimate + budget allocation case | MCKP, shadow price, greedy vs ILP |
| 11 | Timed mock | Marketplace case (surge, supply, spillover) | SUTVA, switchback, geo, budget-split |
| 12 | Timed mock | Full loop: 45-min behavioural + 45-min technical | Everything, cold |

### Resources for this track
- **SQL:** https://datalemur.com/ · https://www.stratascratch.com/ · Nick Singh & Kevin Huo, *Ace the Data Science Interview*.
- **Product/DS cases:** YouTube channel *Data Interview Pro* (Emma Ding) — search *"Emma Ding product case interview data scientist"*. Also *Exponent* on YouTube for PM-adjacent metric cases.
- **A/B testing cases:** re-read Kohavi Ch. 1–4 and 15; then answer "how would you test X" for five products you use.
- **MBB structuring:** *Case in Point* (Cosentino) or **CaseCoach** free materials — https://casecoach.com/. Do at least 6 full cases out loud with a partner. MBB will test structuring and mental math regardless of how technical the role is.
- **Mental math:** https://www.rocketblocks.me/ or plain daily drills. MBB screens on this. Do 10 minutes daily from week 6.
- **Behavioural:** write 8 STAR stories, four of which are *about this project* (a decision you reversed, a result you didn't like, a stakeholder disagreement, a scope cut you made).

### The five artifacts you must be able to produce from memory on a whiteboard
1. The metric tree, three levels deep.
2. `value(i,a) = τ̂(i,a) · margin(i) − cost(i,a)` and the MCKP constraints.
3. The four identification assumptions and which ones randomization gives you.
4. The uplift-decile chart, drawn by hand, with what a good and a bad one look like.
5. The profit-vs-budget curve with all six policies, and where the shadow price crosses 1.

---

## PART 5 — THE ANTI-BLUFF LIST

Things you will be tempted to add. Don't.

| Tempting | Why to skip it |
|---|---|
| Airflow / Dagster orchestration | You have one DAG that runs weekly. A Makefile is the honest answer and interviewers respect it. |
| Spark / dbt / a cloud warehouse | DuckDB on 14M rows is correct engineering. Adding Spark signals you optimise for résumé keywords. |
| Deep learning CATE (DragonNet, TARNet) | You will not beat a cross-fitted DR-learner on 12 anonymised features, and you'll lose a week. Mention you know they exist. |
| MLflow / model registry | Nice, but it adds nothing to the *decision* narrative. Only add it in week 12 if everything else is done. |
| A polished multi-page web app | The dashboard exists to make budget trade-offs tangible. Two controls and three charts. |
| Feature-engineering marathons on anonymised Criteo features | `f0…f11` have no semantics. Effort here has zero return. |
| Hyperparameter tuning to lift Qini by 0.003 | Inside the noise band. Spend that time on the uncertainty quantification instead. |
| Reinforcement learning / contextual bandits | Genuinely the right long-term answer, and genuinely out of scope. Put it in "future work" and be able to say *why* (exploration cost, off-policy evaluation, non-stationarity). |
| A second dataset "for robustness" | One RCT analysed deeply beats two analysed shallowly. |

**And the one thing you must not skip even though it's boring:** uncertainty quantification on the policy value. A point estimate of "+18% incremental margin" with no interval is the difference between a project a senior DS respects and one they don't.

---

## PART 6 — IF YOU ONLY HAVE 10 WEEKS

Compress by cutting *breadth*, never rigour.

- **Merge weeks 2–3 into one week** by generating 6 tables instead of 11 (drop merchants, refunds, cancellations, city-hour capacity) and cutting the marketplace extension to a single capacity constraint.
- **Cut Phase 8 to a memo.** Write `docs/interference_memo.md` explaining SUTVA violation, the three design options, and your choice — with no simulation. You lose one chart; you keep the entire interview answer, which is what actually matters.
- **Cut the optional forecasting companion entirely.** It was already optional.
- **Keep, at full quality:** the leakage test, the A/A calibration histogram, the estimator-recovery benchmark, the random-ranking null baseline, the matched-budget policy comparison, and the bootstrap intervals on policy value. These six are the credibility of the project. Everything else is negotiable.

---

## Master resource index

**Books (buy one: Kohavi)**
- Kohavi, Tang & Xu, *Trustworthy Online Controlled Experiments* — https://www.cambridge.org/core/books/trustworthy-online-controlled-experiments/D97B26382EB0EB2DC2019A7A7B518F59
- Hernán & Robins, *Causal Inference: What If* (free) — https://www.hsph.harvard.edu/miguel-hernan/causal-inference-book/
- Huntington-Klein, *The Effect* (free) — https://theeffectbook.net/
- Cunningham, *Causal Inference: The Mixtape* (free) — https://mixtape.scunning.com/
- Singh & Huo, *Ace the Data Science Interview*

**Free courses / video**
- Brady Neal, *Introduction to Causal Inference* — https://www.bradyneal.com/causal-inference-course · playlist https://www.youtube.com/playlist?list=PLoazKTcS0Rzb6bb9L508cyJ1z-U9iWkA0
- StatQuest — https://www.youtube.com/@statquest · ML playlist https://www.youtube.com/playlist?list=PLblh5JKOoLUICTaGLRoHQDuF_7q2GfuJF
- 3Blue1Brown — https://www.youtube.com/@3blue1brown
- MIT OCW 15.053, Optimization Methods in Business Analytics

**Code handbooks**
- Facure, *Causal Inference for the Brave and True* — https://matheusfacure.github.io/python-causality-handbook/landing-page.html (Ch. 18, 19, 20, 21, 23 are core)
- EconML user guide — https://www.pywhy.org/EconML/spec/estimation/metalearners.html · notebooks https://github.com/py-why/EconML/blob/main/notebooks/Metalearners%20Examples.ipynb
- CausalML — https://github.com/uber/causalml
- scikit-uplift — https://github.com/maks-sh/scikit-uplift · docs https://www.uplift-modeling.com/

**Industry writing (read all of these; they're short and they're what interviewers cite)**
- Uber, *Beyond Prediction: Solving the Multiple Knapsack Problem at Scale* — https://www.uber.com/at/en/blog/solving-multiple-knapsack/
- *Practical Marketplace Optimization at Uber* — https://arxiv.org/abs/2407.19078
- DoorDash, *Switchback Tests Under Network Effects* — https://careersatdoordash.com/blog/switchback-tests-and-randomized-experimentation-under-network-effects-at-doordash/
- DoorDash, *Budget A/B Experimentation* — https://careersatdoordash.com/blog/doordash-ads-uses-budget-a-b-experimentation/
- Liu, Mao & Kang, *Budget-split Design* — https://arxiv.org/abs/2012.08724
- *End-to-End Cost-Effective Incentive Recommendation under Budget Constraint* — https://arxiv.org/abs/2408.11623
- Kohavi, *Pitfalls in Online Controlled Experiments* (slides) — https://exp-platform.com/Documents/2017-05-17EmetricsControlledExperimentsPitfallsKohaviNR.pdf
- Riederer, *Column Names as Contracts* — https://dev.to/emilyriederer/column-names-as-contracts-4la6

**Data**
- Criteo Uplift Prediction Dataset — https://ailab.criteo.com/criteo-uplift-prediction-dataset/ · mirror https://huggingface.co/datasets/criteo/criteo-uplift · loader https://www.uplift-modeling.com/en/latest/api/datasets/fetch_criteo.html
  - v2.1: ~13.98M rows, 12 anonymised features (`f0`–`f11`), binary `treatment`, `exposure`, and two labels `visit` (~4.70%) and `conversion` (~0.29%). Treatment ratio ~85/15.
  - Use `visit` as your primary outcome — the 0.29% conversion base rate leaves almost no power for heterogeneity. Analyse `conversion` as a secondary, and *say* why in the readout.
  - This is advertising exposure data, not churn data. The plan is emphatic about this and it is right: mislabeling it is an instant credibility loss.

**Tools**
- DuckDB — https://duckdb.org/docs/ · Pandera — https://pandera.readthedocs.io/ · scikit-learn calibration — https://scikit-learn.org/stable/modules/calibration.html · LightGBM — https://lightgbm.readthedocs.io/ · OR-Tools — https://developers.google.com/optimization · PuLP — https://coin-or.github.io/pulp/ · Streamlit — https://docs.streamlit.io/
