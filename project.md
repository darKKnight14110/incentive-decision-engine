# Increment — Architecture, Decision Log, and Interview Defence

**Companion to:** `increment_decision_engine_project_plan.md` (what to build) and the tracked evidence in `docs/` and `reports/`.

**What this document is for.** Two things, in this order:
1. The **high-level design** of the system: components, contracts, data flow, and the decision log that explains why each piece is the way it is.
2. The **interview defence**: every non-obvious choice written up as *context → options → decision → consequences*, plus a question bank covering the product, methodological, and executive angles.

**How to use it.** Read §1–§3 before you write code in week 1. Fill in the ADR *Consequences* fields as you actually build (several will change, and the change is the interesting part). Rehearse §7–§8 from week 8 onward.

**A note on numbers.** Every rupee figure in this document is a **placeholder** living in `configs/base.yaml`. They are illustrative until Phase 7 completes. Do not put any of them on a résumé.

---

## 1. The product one-pager

### 1.1 Situation
A consumer marketplace runs a quarterly promotional budget. Today it is spent by rule: everyone in a lifecycle segment gets the same offer, or the offer goes to whoever the CRM tool ranks as most likely to order. Finance sees the spend. Nobody can say what the spend *bought*.

### 1.2 Complication
Most of that budget goes to customers who would have ordered anyway. Those orders get counted as campaign wins. Meanwhile some customers are annoyed by contact and order *less*. Neither effect is visible in a "conversion rate among treated users" report, because that report has no counterfactual in it.

### 1.3 Question
> Given a fixed promotional budget for the coming cycle, which eligible customers should receive an offer, which of {none, small, large} should each receive, and how much incremental contribution margin will that policy generate versus what we do today?

### 1.4 Answer (the shape of it)
A four-stage decision engine:
1. **Measure** the average incremental effect of the offer with a randomized experiment.
2. **Estimate** who the effect is concentrated in, using cross-fitted heterogeneous treatment-effect models.
3. **Convert** those effects into expected incremental contribution margin per customer per action, net of expected redeemed offer cost.
4. **Allocate** the budget by solving a multiple-choice knapsack under budget, contact-volume, frequency-cap, and marketplace-capacity constraints — then validate the policy online with a staged rollout against a persistent holdout.

### 1.5 The decision this system actually makes
**Decider:** Growth/CRM lead, with Finance holding the budget and Ops holding the capacity constraint.
**Cadence:** weekly campaign cycle.
**Alternatives it chooses between:** treat nobody · treat everybody · treat by propensity rank · treat by uplift rank · treat by net-value rank · optimized allocation.
**Evidence that flips the decision:** the profit-vs-budget curve at matched budget, plus the guardrail table.
**What we will not claim:** that this is realized business impact. It is offline policy value on held-out randomized data, with a rollout design attached.

### 1.6 Non-goals
Not a churn model. Not a recommender. Not a pricing engine. Not a dispatch simulator. Not a real-time bidder. Each of these is a reasonable adjacent system and each is explicitly out of scope; §6 ADR-035 records why.

---

## 2. System context

```
                        ┌──────────────────────────────┐
    Finance ──budget───▶│                              │
                        │      DECISION ENGINE         │──▶ Campaign
    Ops ────capacity───▶│  (this project)              │    execution
                        │                              │    (offer sends)
    Growth ─objective──▶│                              │
                        └───────┬──────────────┬───────┘
                                │              │
                    allocation  │              │  readouts
                    + shadow    │              │  + guardrails
                    price       ▼              ▼
                        ┌──────────────┐  ┌──────────────────┐
                        │ Decision UI  │  │ Monitoring &     │
                        │ (Streamlit)  │  │ persistent       │
                        └──────────────┘  │ holdout          │
                                          └──────────────────┘
    Upstream data:
      • Randomized experiment log (Criteo RCT — real, measured)
      • Marketplace event log (synthetic — sessions, orders, offers, capacity)
```

**Stakeholder contract.**

| Stakeholder | What they give the system | What they get back | What would make them reject it |
|---|---|---|---|
| Finance | Budget ceiling, margin assumptions | Expected incremental margin, ROI, shadow price of the next rupee | Simulated results presented as realized; no uncertainty |
| Growth / CRM | Objective, offer catalogue, frequency policy | Ranked allocation, segment mix, expected lift vs today | A black box with no explanation of who gets what and why |
| Ops | City-hour capacity, SLA thresholds | A policy that respects capacity; guardrail alerts | A campaign that spikes demand into a supply-constrained hour |
| Data Science peers | Nothing | Reproducible pipeline, model card, honest limitations | AUC used as an uplift metric; unmatched budget comparisons |
| Legal/Trust | Contact-frequency policy | Frequency caps enforced as hard constraints | Users contacted beyond policy |

---

## 3. High-level design

### 3.1 The five planes

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. DATA PLANE                                                            │
│    generate_marketplace.py → DuckDB → sql/*.sql → build_features.py      │
│    Output contract: eligible_users.parquet                               │
│      one row per (user_id, decision_ts); all features strictly pre-      │
│      treatment; validated by Pandera; leakage test must pass             │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. MEASUREMENT PLANE  (what IS the effect?)                              │
│    diagnostics.py (SRM, balance) → estimation.py (ITT, CI) → power.py    │
│    Output contract: ate_estimate{point, se, ci, n_t, n_c, srm_p}         │
│    GATE: SRM p < 0.001 ⇒ pipeline halts. No downstream stage runs.       │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. LEARNING PLANE  (who is the effect in?)                               │
│    simulate.py + estimators.py  ──validate──▶  meta_learners.py,         │
│    dr_learner.py (cross-fitted)                                          │
│    Output contract: tau_hat[n_users × n_actions] + fold assignments      │
│    GATE: must beat constant-effect baseline on held-out policy value,    │
│          or the report concludes "no reliable heterogeneity established" │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. DECISION PLANE  (what do we do about it?)                             │
│    value.py (τ̂ → ₹) → optimize.py (MCKP/ILP) ← policy_constraints.yaml   │
│    Output contract: allocation{user_id, action, expected_value,          │
│                     expected_cost}, plus λ (shadow price of budget)      │
│    GATE: compared to all baselines at MATCHED budget, with intervals     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. EVALUATION & CONTROL PLANE                                            │
│    evaluation.py (Qini/AUUC/DR policy value) · capacity.py ·             │
│    geo_experiment.py · drift.py · realized_value.py · dashboard.py       │
│    Output contract: policy_value{point, boot_ci} per policy per budget   │
└─────────────────────────────────────────────────────────────────────────┘
```

**Design rule that holds the whole thing together:** each plane consumes only the previous plane's declared output contract. If the learning plane needs a column the data plane doesn't publish, you add it to the data plane and re-run the leakage test — you do not reach around and join it in a notebook. This is what makes the Phase 2 gate ("rebuild with one command") true and it is what a senior interviewer probes for.

### 3.2 The weekly run sequence

```
 Mon 02:00  rebuild feature table as of decision_ts = Mon 00:00
            └─ leakage test, data contracts, row-count invariance
 Mon 02:30  score τ̂ for each eligible user × each action (cross-fitted models)
 Mon 02:45  compute value(i,a) using current margin + redemption assumptions
 Mon 03:00  read budget + capacity + frequency state → solve MCKP
 Mon 03:15  carve out persistent holdout (2%) BEFORE allocation is applied
 Mon 03:20  emit allocation + λ + expected value; write to campaign queue
 Mon 09:00  human review in dashboard: budget utilisation, segment mix,
            change vs last week, guardrail forecast
 Ongoing    monitoring: realized margin vs expected, calibration drift,
            allocation drift, guardrails; 14-day outcome window closes
```

Two things in that sequence do disproportionate work in an interview: **the holdout is carved before allocation** (so it is a true random sample of the eligible population, not the leftovers), and **λ is emitted alongside the allocation** (so Finance can be told the marginal return of the next rupee, not just the total).

### 3.3 Two data sources, deliberately never merged

| | Criteo Uplift v2.1 | Synthetic marketplace |
|---|---|---|
| Nature | **Real randomized experiment** | **Simulated**, seeded, known DGP |
| ~Size | 13.98M rows, 12 anonymised features | Configurable; ~200k users |
| Treatment | Advertising exposure eligibility (85/15) | Multi-action offers |
| Outcome | `visit` (~4.7%), `conversion` (~0.29%) | Orders, margin, cancellations |
| Used for | ATE, HTE estimation, Qini, held-out policy value | SQL layer, funnels, cohorts, unit economics, multi-action, capacity, monitoring |
| Label in every chart | **measured** / **estimated** | **simulated** |

They are never joined. The Criteo data carries the causal claim; the synthetic data carries the business plumbing. Any result that requires both is presented as an illustration with the synthetic component explicitly flagged. Getting sloppy about this is the fastest way to lose a technical interviewer, and being *visibly* disciplined about it is one of the strongest signals the project sends.

---

## 4. Data architecture

### 4.1 Table grain declarations

| Table | Grain | PK | Pre-treatment? |
|---|---|---|---|
| `users` | one row per user | `user_id` | signup attributes only |
| `sessions` | one row per session | `session_id` | yes, filtered by ts |
| `orders` | one row per order | `order_id` | yes, filtered by ts |
| `order_items` | one row per order line | `order_id, line_no` | yes |
| `merchants` | one row per merchant | `merchant_id` | yes |
| `offers` | one row per offer definition | `offer_id` | catalogue |
| `exposures` | one row per (user, campaign, send) | `exposure_id` | **treatment** |
| `redemptions` | one row per redeemed offer | `redemption_id` | **post-treatment** |
| `cancellations` | one row per cancelled order | `order_id` | **post-treatment** |
| `refunds` | one row per refund | `refund_id` | **post-treatment** |
| `experiment_assignments` | one row per (user, experiment) | `user_id, experiment_id` | **treatment** |
| `city_hour_capacity` | one row per (city, hour) | `city_id, hour_ts` | context |
| `eligible_users` | **one row per (user, decision_ts)** | `user_id, decision_ts` | modeling table |

The bolded post-treatment tables are the feature blocklist. The executable
`POST_TREATMENT_SOURCES` constant in `src/data/validate_data.py` is enforced at
the feature-table boundary, and the leakage tests assert that no published
feature contains a post-treatment source column or event at/after the
decision timestamp.

### 4.2 Point-in-time correctness

Every feature for user *i* is computed over events with `event_ts < decision_ts(i)`, strict inequality. Implemented as a DuckDB `ASOF JOIN` (or an explicit correlated aggregate with a `<` predicate) rather than a date-level join, because a same-day `<=` join silently admits events that occurred hours after the decision.

The test that proves it: for a sample of users, shift `decision_ts` backwards by one day and assert that every rolling feature is non-increasing in count. A feature that grows when you move the decision *earlier* is leaking.

### 4.3 Eligibility

Eligibility is a **rule layer, not a model layer**, and it is evaluated before scoring:

```
eligible(i) = has_prior_order(i)
            AND NOT contacted_within(i, 14d)          # frequency policy
            AND city_active(i)                        # ops
            AND NOT suppressed(i)                     # consent / legal
            AND account_age(i) >= 7d                  # avoid new-user confound
```

Keeping this separate from the optimizer matters for two reasons. It means the population is identical across every policy comparison (so a matched-budget comparison is meaningful), and it means legal/consent rules are enforced by construction rather than by a soft penalty a solver could trade away.

---

## 5. The metric contract

### 5.1 Metric tree

```
Incremental contribution margin per eligible customer     ← PRIMARY (the OEC)
│
├── Incremental conversion rate  (τ, the causal quantity)
│   ├── Baseline conversion propensity      [predictive, not causal]
│   └── Treatment responsiveness            [causal, heterogeneous]
│
├── Contribution margin per converted order
│   ├── AOV
│   ├── Variable cost rate (COGS, payment, delivery, support)
│   └── Refund / cancellation drag
│
└── Expected offer cost
    ├── Offer face value
    ├── Redemption rate | exposure
    └── Cannibalisation (offers redeemed on orders that would have happened)
```

### 5.2 Every metric, fully specified

| Metric | Numerator | Denominator | Grain | Window | Role |
|---|---|---|---|---|---|
| Incremental contribution margin per eligible customer | Σ (margin under policy − margin under no-offer) | eligible customers | user | 14d post-decision | **Primary** |
| Incremental conversion rate | conv(T) − conv(C) | eligible customers per arm | user | 14d | Driver |
| Cost per incremental order | total offer cost | incremental orders | campaign | 14d | Efficiency |
| Campaign ROI | incremental margin − offer cost | offer cost | campaign | 14d | Efficiency |
| Repeat-purchase rate | users with ≥2 orders | treated users | user | 28d | Secondary |
| AOV | order value | orders | order | 14d | Secondary |
| Cancellation rate | cancelled orders | orders | order | 14d | **Guardrail** |
| Refund rate | refunded orders | orders | order | 14d | **Guardrail** |
| Negative-margin order share | orders with margin < 0 | orders | order | 14d | **Guardrail** |
| p95 delivery time | — | city-hour | city-hour | daily | **Guardrail** |
| Contacts per user per 14d | contacts | user | user | 14d | **Guardrail** |
| Budget utilisation | spend | budget | campaign | cycle | Diagnostic |
| Shadow price λ | ∂(margin)/∂(budget) | — | campaign | cycle | Diagnostic |

**Why "per eligible customer" and not "per treated customer".** Because the denominator is the population the decision applies to. Per-treated denominators reward policies that treat few, easy customers and make every policy look good. This one choice is worth stating explicitly in an interview — it is the kind of thing that separates people who have shipped a campaign from people who have read about one.

---

## 6. Decision log

Thirty-five decisions, in the order they get made. Each is written as **Context → Options → Decision → Why → Consequences → Soundbite**. The soundbite is the two-sentence version you say out loud when an interviewer asks "why did you do it that way?"

Fill in `Consequences` with what actually happened as you build. A decision log where every consequence is a prediction reads as theory. One where three of them say "this turned out to be wrong, and here's what I changed" reads as experience.

---

### Framing decisions

**ADR-001 · Frame this as a decision engine, not an uplift model**
- **Context.** The natural instinct is to build "an uplift model" and report its Qini. That is a model demo.
- **Options.** (a) Uplift model with Qini as the headline. (b) Targeting policy with policy value as the headline. (c) Full decision system with a constrained allocation and a budget curve.
- **Decision.** (c).
- **Why.** Every interviewer at MBB, Uber, or an Eternal-style product org evaluates whether you can connect a model to a decision with a constraint on it. Qini is an intermediate diagnostic; incremental margin under a budget is the deliverable. The optimization layer is also what makes the project genuinely uncommon — many candidates have an uplift notebook; almost none have a constrained allocator with a shadow price.
- **Consequences.** Adds ~2 weeks (Phase 7 + 8). Requires an explicit, defensible cost model, which is a new source of assumption risk.
- **Soundbite.** "The model isn't the product. The product is a weekly allocation of a fixed budget, and the model is one input to it."

**ADR-002 · Objective is incremental contribution margin, not incremental conversions**
- **Context.** Conversions are easier to measure and easier to model.
- **Options.** (a) Maximise incremental conversions. (b) Maximise incremental revenue. (c) Maximise incremental contribution margin net of offer cost.
- **Decision.** (c), with incremental conversions retained as a driver metric.
- **Why.** Conversions ignore that a converted order can be margin-negative once the offer is paid out. Revenue ignores variable cost. Only margin nets out the thing Finance actually cares about. It also makes the trade-off between small and large offers meaningful — a large offer buys more conversions and destroys more margin per conversion.
- **Consequences.** Introduces dependence on a margin assumption (22% placeholder) and a redemption assumption. Both go in the assumptions register with sensitivity ranges, and the headline result is re-run at the low and high end of each.
- **Soundbite.** "Optimising conversions would have told me to send the large offer to everyone. Optimising margin tells me the large offer only pays for itself in about the top two deciles of estimated uplift."

**ADR-003 · Two data sources, structurally separated**
- **Context.** Criteo is a real RCT with anonymised features and no business fields. A realistic marketplace needs SQL, funnels, unit economics, capacity — none of which Criteo has.
- **Options.** (a) Criteo only; invent business meaning for `f0`–`f11`. (b) Synthetic only. (c) Both, kept apart with explicit labelling.
- **Decision.** (c).
- **Why.** (a) is dishonest and an interviewer will catch it in one question ("what is f3?"). (b) means every causal result is something I made up, so nothing is validated against reality. (c) lets the causal claim rest on genuinely randomized real data while the engineering and economics rest on a simulation I can fully describe.
- **Consequences.** Two pipelines, more surface area, and the discipline burden of labelling every chart. Worth it.
- **Soundbite.** "The causal claim comes from a real randomized experiment. The business plumbing comes from a simulator whose data-generating process I wrote and can show you. I never mix them in the same number."

**ADR-004 · Randomization is the identification strategy; no propensity matching on the RCT**
- **Context.** Covariate balance checks will show a couple of imbalanced features by chance across 12 features.
- **Options.** (a) Re-match/re-weight to fix the imbalance. (b) Report balance and proceed with the randomized comparison. (c) Skip balance checks.
- **Decision.** (b).
- **Why.** Matching on randomized data conditions on realised chance imbalance, which can *introduce* bias and definitely invalidates the design-based standard errors. Balance tables are a diagnostic for *broken randomization* (which shows up as SRM or systematic imbalance), not a licence to re-randomize post hoc. Skipping checks entirely forfeits the ability to detect a broken assignment.
- **Consequences.** I must be able to explain the difference between "imbalance as evidence of a bug" and "imbalance as something to correct." That distinction is itself an interview asset.
- **Soundbite.** "Randomization is what I paid for. Matching on top of it spends that and gets nothing back. I report balance to check the randomization worked, not to fix it."

**ADR-005 · A single explicit decision timestamp per user**
- **Context.** Features must be pre-treatment. Without a decision timestamp there is nothing to be "pre" of.
- **Options.** (a) Date-level features with a daily join. (b) Explicit `decision_ts` per user with strict `<` as-of joins.
- **Decision.** (b), implemented via DuckDB `ASOF JOIN`.
- **Why.** Date joins admit same-day post-decision events. In a 14-day outcome window, a few hours of leakage can move a small uplift signal materially, and it is undetectable from model metrics alone.
- **Consequences.** Slower feature builds; requires the shift-the-timestamp regression test described in §4.2.
- **Soundbite.** "Every feature is computed with a strict less-than against a per-user decision timestamp, and there's a test that fails if someone changes it to less-than-or-equal."

**ADR-006 · Discrete three-action space, not a continuous discount**
- **Context.** Real platforms sometimes optimise a continuous discount depth.
- **Options.** (a) Binary treat/don't-treat. (b) Three discrete actions {none, small, large}. (c) Continuous discount %.
- **Decision.** (b).
- **Why.** Binary can't demonstrate the multiple-choice structure (the interesting constrained-optimization case) and can't show the small-vs-large trade-off. Continuous requires a dose-response causal model plus monotonicity/smoothness constraints, which is a research project and would swamp the rest. Three actions gives an MCKP — the same formulation Uber describes in production — at a fraction of the cost.
- **Consequences.** Criteo has a binary treatment only, so multi-action results are simulated and labelled as such. The Criteo analysis carries the binary causal claim; the synthetic layer carries the multi-action allocation.
- **Soundbite.** "Three actions is the smallest action space that makes the problem a multiple-choice knapsack rather than a sort. That's the structure I wanted to demonstrate."

**ADR-007 · Eligibility is a rule layer outside the model**
- **Context.** Consent, frequency policy, and active-city rules could be encoded as features or as constraints.
- **Options.** (a) Let the model learn them. (b) Soft penalties in the objective. (c) Hard pre-filter.
- **Decision.** (c).
- **Why.** Legal and consent rules must be enforced by construction — a solver that can trade a compliance penalty against margin will eventually do it. A hard pre-filter also fixes the population, which is what makes matched-budget policy comparison valid.
- **Consequences.** The eligible population shrinks; I must report eligible-population size prominently since it is the denominator of the primary metric.
- **Soundbite.** "Anything legal or contractual is a filter, not a feature. The optimizer is never allowed to price a compliance violation."

**ADR-008 · 14-day outcome window, decision-anchored attribution**
- **Context.** Conversions arrive with a lag; longer windows capture more effect but delay every decision and admit more contamination from subsequent campaigns.
- **Options.** (a) 7 days. (b) 14 days. (c) 30 days.
- **Decision.** 14 days, with the lag curve reported.
- **Why.** 7 days truncates a meaningful share of a delivery-marketplace repeat cycle. 30 days overlaps the next campaign cycle, so a user could be treated again inside their own outcome window — that's interference with yourself. 14 days matches the weekly cadence with two cycles of buffer and matches the frequency cap.
- **Consequences.** Some genuine effect is truncated, so the estimate is conservative. I report the cumulative-conversion-by-day curve so the reader can see how much is being left out. Any early read before day 14 is explicitly labelled incomplete.
- **Soundbite.** "Fourteen days, chosen so the window closes before the same user can be re-treated. I show the lag curve so you can see what I'm giving up at the tail."

**ADR-009 · Guardrails are a harm hypothesis, not a checklist**
- **Context.** It is easy to list guardrails; harder to say why each one is there.
- **Decision.** Five guardrails, each with a stated mechanism: cancellation rate (offer-driven impulse orders cancel more), refund rate (same), negative-margin order share (large offers on small baskets), p95 delivery time (demand spike into constrained supply), contacts per user (annoyance → unsubscribe → permanent loss of a channel).
- **Why.** A guardrail without a mechanism can't have a threshold set for it, and can't be defended when it trips.
- **Consequences.** The contact-frequency guardrail becomes a hard optimizer constraint (ADR-025); the rest are monitored with rollback thresholds.
- **Soundbite.** "Each guardrail answers 'what breaks if this campaign works too well?' The delivery-time one is the interesting one, because it's the mechanism by which a customer-level win becomes a marketplace-level loss."

---

### Data and engineering decisions

**ADR-010 · DuckDB, not Postgres or Spark**
- **Options.** (a) SQLite. (b) DuckDB. (c) PostgreSQL. (d) Spark.
- **Decision.** DuckDB, with the SQL written to stay close to standard so a Postgres port is trivial.
- **Why.** 14M rows is an in-process analytical workload. DuckDB gives columnar performance, `ASOF JOIN` (which is exactly the point-in-time primitive this project needs), direct Parquet reads, and zero infrastructure. Spark here would be a keyword, not an engineering choice, and a good interviewer will say so.
- **Consequences.** No multi-user concurrency and no server. Neither is needed. I keep a note in the README on what would change at 100x scale (partitioned Parquet + Spark or a warehouse; the SQL logic is unchanged).
- **Soundbite.** "DuckDB, because the dataset fits in memory and `ASOF JOIN` gives me point-in-time correctness natively. I can tell you what I'd change at a hundred times the scale, but adding Spark here would have been a costume."

**ADR-011 · SQL-first transformations, thin notebooks**
- **Decision.** All aggregation, cohorting, and feature computation lives in `sql/` or in tested `src/` functions. Notebooks import and narrate.
- **Why.** Notebooks are not testable, not diffable, and not rebuildable. The Phase 2 gate ("rebuild from raw with one command") is only achievable if the logic isn't trapped in cells. Separately: SQL is what gets tested in the interview, so writing the hard parts in SQL is deliberate practice.
- **Consequences.** Slower iteration early. Pays back from week 4 onward.
- **Soundbite.** "If it's in a notebook, it isn't tested, so nothing that produces a number I'd quote lives in a notebook."

**ADR-012 · Data contracts as a build gate**
- **Decision.** Executable typed dataframe contracts plus set-based SQL assertions run in CI. Failures block the build.
- **Why.** The single highest-consequence class of error in this project is silent: a join that fans out, a duplicate assignment, a post-treatment feature. None of these produce an exception; they produce a plausible wrong number. Contracts turn silent errors into loud ones.
- **Consequences.** ~4 hours of setup. Catches the fan-out bug that everyone gets at least once.
- **Soundbite.** "I injected 0.3% duplicate assignments into my own generator so the tests would have something to catch, and then I checked they caught it."

---

### Experimentation decisions

**ADR-013 · Primary metric denominator is the eligible population**
- Covered in §5.2. Recorded here because it is a decision, not a definition.
- **Soundbite.** "Per eligible customer, not per treated customer, because the decision applies to everyone eligible and I don't want a policy to look good by treating fewer, easier people."

**ADR-014 · Intent-to-treat, not per-protocol**
- **Context.** Criteo distinguishes `treatment` (entered the RTB auction) from `exposure` (actually won the auction and showed the ad).
- **Options.** (a) ITT on `treatment`. (b) Effect-on-the-treated using `exposure`. (c) Instrumental-variables / CACE using treatment as an instrument for exposure.
- **Decision.** (a) as primary, with (c) noted as the correct route to the exposure effect and implemented only if time permits.
- **Why.** `exposure` is **post-randomization**. Comparing exposed vs unexposed users is an observational comparison — whoever wins an auction for you is systematically different. ITT answers the decision I actually control: "should I put this user into the campaign?" That is the policy lever, so it is the right estimand.
- **Consequences.** ITT dilutes the effect by the exposure rate, so my ATE is smaller than the "true" effect on the exposed. I say this explicitly rather than quietly using the bigger number.
- **Soundbite.** "Exposure is post-treatment, so conditioning on it breaks randomization. ITT is also the right estimand anyway, because entering someone into the campaign is the decision I get to make — winning the auction isn't."

**ADR-015 · `visit` as primary outcome, `conversion` as secondary**
- **Context.** Criteo v2.1 has `visit` at ~4.70% and `conversion` at ~0.29%.
- **Decision.** Primary analysis and all heterogeneity modeling on `visit`; `conversion` analysed for ATE only, with power stated.
- **Why.** At a 0.29% base rate, the variance of any decile-level uplift estimate swamps plausible heterogeneity — you would be modeling noise and the Qini curve would look like a random walk. Choosing the outcome you have power for, and *saying why*, is better methodology than modeling the outcome that sounds more commercial.
- **Consequences.** The economic layer requires mapping visits to margin, which is a stated assumption rather than a measurement. Flagged in every downstream figure.
- **Soundbite.** "I ran the MDE calculation before choosing the outcome. At a 0.29% base rate I don't have the power to estimate heterogeneity, so heterogeneity runs on visits and conversions get an ATE with an honest interval."

**ADR-016 · Regression adjustment for precision only, pre-specified**
- **Options.** (a) Raw difference in means. (b) Pre-specified covariate-adjusted (CUPED-style) estimator as primary. (c) Adjusted as a secondary precision comparison.
- **Decision.** (a) as primary, (c) reported alongside.
- **Why.** On randomized data, adjustment reduces variance but does not remove bias, and the temptation to pick whichever specification gives significance is real. Keeping the unadjusted estimate as headline removes the degree of freedom; showing the adjusted one demonstrates I know the technique and quantifies what it bought.
- **Consequences.** Slightly wider primary interval. Full transparency in exchange.
- **Soundbite.** "Adjustment is a variance play, not a bias play. I pre-specified it, reported both, and led with the unadjusted number so nobody has to wonder whether I went shopping for a specification."

**ADR-017 · SRM is a hard halt**
- **Decision.** SRM chi-square p < 0.001 stops the pipeline. No effect estimate is produced.
- **Why.** SRM means the assignment mechanism is broken, which means every downstream number is untrustworthy regardless of how good it looks. Continuing "just to see" is how bad results get shipped. Microsoft found roughly 8% of experiments affected; this is not a rare failure mode.
- **Consequences.** Requires a documented triage path (bot filtering, logging asymmetry, redirect loss, triggering bugs) so a halt is actionable rather than a dead end.
- **Soundbite.** "SRM is a seatbelt. If it fires I don't analyse the experiment, I debug the assignment."

---

### Modeling decisions

**ADR-018 · Build the propensity model deliberately, as a strawman**
- **Context.** A propensity/likelihood-to-order model is what most CRM tools actually use for targeting.
- **Options.** (a) Skip it and go straight to uplift. (b) Build it as the incumbent baseline.
- **Decision.** (b).
- **Why.** Without it there is nothing to beat, and "uplift is better than propensity" is an assertion rather than a measurement. Quantifying how much margin the incumbent approach wastes on sure-things is the single most persuasive business number in the project — it is the *reason the project exists*, stated numerically.
- **Consequences.** One extra week. Produces `docs/why_propensity_is_not_uplift.md`, which does heavy interview work.
- **Soundbite.** "The propensity model isn't a mistake I made, it's the incumbent I'm measuring against. It's how I put a number on the money currently spent on customers who'd have ordered anyway."

**ADR-019 · Calibration is mandatory before any probability meets a rupee**
- **Decision.** All probability outputs are calibrated on a held-out fold (isotonic if n is large, Platt otherwise) and a reliability diagram is published.
- **Why.** The value function multiplies a probability by a margin. A model that ranks perfectly but is systematically overconfident produces confidently wrong money and an optimizer that overspends. Ranking metrics are blind to this.
- **Consequences.** Costs a fold of data. Adds a required figure.
- **Soundbite.** "I multiply these probabilities by rupees, so ranking quality isn't enough — I need the number 0.04 to actually mean four percent, and here's the reliability diagram that shows it does."

**ADR-020 · Validate estimators on known ground truth before touching real data**
- **Decision.** Phase 5 runs before Phase 6, non-negotiable. Four DGPs (constant effect, heterogeneous effect, confounded, poor overlap), 500 replications, measuring bias and 95% interval coverage for naive / regression-adjusted / IPW / AIPW.
- **Why.** On real data you never see the truth, so a broken estimator looks exactly like a small effect. Simulation is the only place you can prove your implementation is correct. This phase is also the single most differentiating part of the repository: almost nobody does it, and it's the thing that lets you say your numbers are trustworthy rather than just hoping.
- **Consequences.** A week that produces no business result. Buys the credibility of every business result that follows.
- **Soundbite.** "I don't trust an estimator I haven't watched recover a known answer — and, just as important, I want to see it visibly fail when overlap is bad, because a method that never looks worried is a method that's lying to me."

**ADR-021 · Meta-learner ladder, stop when the gains stop**
- **Options.** Jump straight to a causal forest / DragonNet, or climb a ladder.
- **Decision.** Constant-effect → S → T → X → cross-fitted DR-learner, in that order, each evaluated on held-out policy value, stopping when the improvement is inside the bootstrap band.
- **Why.** The constant-effect policy is the honest null: "there is one ATE, spend the budget on whoever is cheapest to convert." If a sophisticated learner cannot beat that on held-out policy value, the correct conclusion is that reliable heterogeneity was not established — and reporting that is far stronger than a Qini number with no benchmark. The X-learner is included specifically because Criteo is 85/15 imbalanced, which is the regime X-learner was designed for.
- **Consequences.** More code. Produces the comparison table that makes the model-selection argument.
- **Soundbite.** "I picked the simplest learner that beat the one below it by more than its own uncertainty. The DR-learner won, but the honest headline is that the gap over the T-learner was smaller than people usually assume."

**ADR-022 · Cross-fitting is mandatory for the DR-learner**
- **Decision.** K-fold cross-fitting (K=5) for all nuisance models; folds assigned at user level and reused consistently; preprocessing fitted inside the fold.
- **Why.** Pseudo-outcomes built from in-sample nuisance predictions are contaminated by the same noise the second-stage model then fits, producing a CATE that looks structured and is not. No downstream metric catches this reliably.
- **Consequences.** 5x fit cost. Fold assignments must be persisted so evaluation uses out-of-fold predictions.
- **Soundbite.** "Without cross-fitting the DR pseudo-outcome carries the first-stage overfit into the second stage, and the resulting heterogeneity is an artefact. The Qini curve looks fine, which is exactly why it has to be structural rather than something you check for."

**ADR-023 · Never AUC. Qini, AUUC, and doubly robust policy value**
- **Decision.** Evaluation is (i) actual treated-minus-control uplift by predicted-uplift decile, (ii) Qini and AUUC against a random-ranking null, (iii) doubly robust policy value on held-out randomized data as the primary decision metric.
- **Why.** The CATE label is unobservable, so no prediction metric can score it. Policy value is the only quantity that answers the actual question ("what would we have earned if we'd followed this policy?"). Qini and the decile chart are the diagnostics that make policy value interpretable to a non-technical reader.
- **Consequences.** Requires held-out randomized data reserved from the start.
- **Soundbite.** "AUC scores a label I never observe. Policy value scores the decision I'd actually make, and it's the only number I'd let anyone quote."

**ADR-024 · A random-ranking null baseline is mandatory**
- **Context.** A normalized AUUC of ~0.5 is what pure noise scores, and a positive Qini from a noise ranking is entirely possible in a single sample.
- **Decision.** Score a uniform-random ranking through the identical evaluation path and plot it alongside every model, with bootstrap bands on both.
- **Why.** Without it, "Qini = 0.11" is uninterpretable. With it, the reader can see whether the model has separated from noise.
- **Consequences.** May reveal that it hasn't. That is a result, and §9 explains how to present it.
- **Soundbite.** "Before I believed my Qini, I scored a column of random numbers through the same pipeline. If my model's interval overlapped the noise ranking's, I'd have said so."

**ADR-025 · Bootstrap at the user level, on the evaluation not the fit**
- **Decision.** Resample users with replacement; recompute policy value, Qini, and the profit curve; report percentile intervals. Model refitting is *not* inside the bootstrap loop, and this is stated explicitly.
- **Why.** Resampling rows of an order-level table understates variance because a user's orders are correlated. Refitting inside the bootstrap would be more complete but costs ~1000 model fits; the honest move is to do the cheaper version and label what it does and does not capture (it captures evaluation-sample uncertainty, not model-selection uncertainty).
- **Consequences.** Intervals are slightly optimistic. Stated in the model card.
- **Soundbite.** "The intervals cover sampling variation in the evaluation set, not model-selection variation. I'd need a nested bootstrap for that and I say so rather than letting the reader assume."

---

### Decision-layer and optimization decisions

**ADR-026 · Cost is expected redeemed cost, not exposure cost**
- **Options.** (a) Charge the offer's face value to every treated user. (b) Charge face value × P(redeem | exposed).
- **Decision.** (b), with (a) shown as a sensitivity.
- **Why.** Coupons cost money when they are used. Charging face value to everyone overstates cost by roughly 2–3x and pushes the optimizer to treat far too few people. But (b) creates a subtle trap: redemption is itself an outcome influenced by treatment, so it is estimated, not known — I treat it as an assumption with a range rather than a measurement.
- **Consequences.** Redemption rate becomes one of the highest-sensitivity parameters in the whole model. It gets its own row in the tornado chart.
- **Soundbite.** "I charge expected redeemed cost, not exposure cost, because that's what Finance actually pays. It's also the assumption my result is most sensitive to, which is why there's a sensitivity chart for it."

**ADR-027 · Formulate as a multiple-choice knapsack, solved as an ILP**
- **Decision.**
  ```
  maximise    Σ_i Σ_a  v(i,a) · x(i,a)
  subject to  Σ_a x(i,a) = 1                      ∀i     (exactly one action per customer)
              Σ_i Σ_a c(i,a) · x(i,a) ≤ B                (budget)
              Σ_i Σ_{a≠none} x(i,a)   ≤ K                (contact volume)
              Σ_{i∈g} Σ_{a≠none} x(i,a) ≤ K_g    ∀g      (frequency cap / segment)
              Σ_{i∈(c,h)} Σ_a q(i,a)·x(i,a) ≤ Cap(c,h)   (city-hour capacity)
              x(i,a) ∈ {0,1}
  ```
- **Why.** This is the smallest formulation that captures every real constraint. Naming it as MCKP connects the project directly to how Uber describes its production incentive allocator, which is a useful anchor in an interview.
- **Consequences.** With per-customer binaries this is large. See ADR-028.
- **Soundbite.** "Exactly-one-action per customer plus a shared budget makes it a multiple-choice knapsack. That's the same structure Uber describes for their incentive allocator, and it's why a simple sort isn't sufficient once capacity and frequency constraints are in."

**ADR-028 · Three solvers, cross-checked; Lagrangian is the one that ships**
- **Options.** (a) ILP only. (b) Greedy ratio heuristic only. (c) All three: ILP, Lagrangian/threshold, greedy — cross-validated against each other.
- **Decision.** (c). ILP for correctness on a subsample; Lagrangian relaxation (bisect on λ until the budget binds) for full scale; greedy as the naive benchmark. Assert all three agree within tolerance on a small instance — this is the optimizer's unit test.
- **Why.** ILP with millions of binaries is impractical and unnecessary: with a single budget row the LP relaxation has at most one fractional variable, so the threshold rule is essentially optimal. Lagrangian also decomposes per customer, so it scales trivially and can be served online. Greedy exists to answer "did the optimizer earn its complexity?" — and if the answer is "it beat greedy by 0.4%", that is a valuable and honest finding.
- **Consequences.** Three code paths to maintain. The cross-check test is worth it on its own.
- **Soundbite.** "I solve it three ways and make them agree. The ILP proves correctness on a small instance, the Lagrangian scales and gives me the shadow price for free, and greedy tells me whether any of it was worth doing."

**ADR-029 · λ, the shadow price of budget, is a first-class output**
- **Decision.** Every run emits λ alongside the allocation, and the profit-vs-budget curve is derived by sweeping λ rather than re-solving from scratch.
- **Why.** λ is the marginal incremental margin per extra rupee of budget. It converts "here is the optimal allocation" into "here is how much more budget you should ask for, and here is where the next rupee stops paying for itself." That is the sentence a CFO and an MBB partner both want. It is also the cheapest way to generate the full budget curve.
- **Consequences.** Requires explaining duality clearly in the exec doc without using the word "dual".
- **Soundbite.** "The optimizer's most useful output isn't the allocation, it's λ. It says the next rupee of budget returns ₹λ of margin, so it tells you when to stop funding the campaign — which is a question the allocation alone can't answer."

**ADR-030 · All policy comparisons at matched budget, same eligible population**
- **Decision.** Treat-none, treat-all, random, propensity, uplift-rank, net-value-rank, and optimized are evaluated on the identical eligible population, at the identical budget, with the identical value and cost model. Where treat-all exceeds the budget, it is shown both unconstrained (labelled) and budget-truncated.
- **Why.** Unmatched comparisons are the most common way portfolio projects lie, usually unintentionally. A policy that spends 3x more will win on total margin and lose on ROI, and reporting whichever framing flatters the model is indefensible.
- **Consequences.** Treat-all often can't fit the budget, which requires careful presentation.
- **Soundbite.** "Same population, same budget, same cost model, or it isn't a comparison. Where treat-all doesn't fit the budget I show both versions and label them."

---

### Marketplace decisions

**ADR-031 · SUTVA is treated as violated, not assumed**
- **Context.** Randomization gives unconfoundedness. It does not give SUTVA.
- **Decision.** Explicitly model and demonstrate interference: simulate a city-hour where treating enough customers pushes demand past courier capacity, degrading delivery time and raising cancellations for *everyone* in that cell, including controls.
- **Why.** This is the conceptual centre of marketplace data science, and the ability to say "my user-level ATE is biased upward and here is the mechanism" is the thing that distinguishes a marketplace-DS candidate. The bias direction matters: with congested shared supply, user-level tests generally **overstate** a demand-stimulating treatment, because the control group absorbs the congestion externality.
- **Consequences.** Requires the capacity constraint (ADR-032) and the geo-design memo (ADR-033).
- **Soundbite.** "Randomization buys me unconfoundedness. It doesn't buy me SUTVA, and in a marketplace SUTVA is the assumption that actually fails — treating you consumes the courier that would have delivered to the control user next door."

**ADR-032 · Capacity enters the optimizer, not just the analysis**
- **Decision.** Incremental orders per city-hour ≤ available capacity, as a hard constraint, with delivery-time and cancellation guardrails checked post-solve.
- **Why.** An individually profitable policy can be collectively value-destroying. Showing the unconstrained policy overloading three city-hours and turning net-positive into net-negative once guardrails are priced is the most compelling chart in Phase 8.
- **Consequences.** Requires a capacity model in the simulator and a mapping from users to city-hours. Kept deliberately coarse.
- **Soundbite.** "The capacity constraint is in the optimizer because it's a real constraint, not a post-hoc filter. Without it the policy is optimal for the customer and wrong for the marketplace."

**ADR-033 · Cluster-randomized geo design for validation; switchback and budget-split considered**
- **Options.** (a) User-level A/B. (b) Geo/cluster randomization. (c) Switchback (time × region). (d) Budget-split.
- **Decision.** Geo/cluster randomization for the validation experiment, with switchback and budget-split documented and rejected for stated reasons.
- **Why.** User-level fails on interference (ADR-031). Switchback handles simultaneous interference but suffers carryover — a promotion's effect persists into the next window, which is precisely the failure mode for incentives, and DoorDash reports switchback MDEs materially worse than budget-split. Budget-split is arguably the best answer for a spend-mediated intervention but requires platform infrastructure I'm not simulating. Geo is implementable, defensible, and the trade-off I'm accepting (low power from ~40 clusters) is one I can quantify.
- **Consequences.** Must report cluster-robust standard errors and an honest MDE, which will be uncomfortably large. Saying "this design can only detect a 6% lift and here's what I'd do about it" is a strength.
- **Soundbite.** "Geo, because the interference channel is local supply. I'd prefer budget-split for a spend-mediated treatment — DoorDash's write-up on it is convincing — but that needs platform support. Switchback I rejected on carryover: promotions persist past the window boundary."

**ADR-034 · Short-run effects only; equilibrium is out of scope and stated**
- **Decision.** All estimates are short-run partial-equilibrium effects. The document states that at full rollout, merchant behaviour, courier supply, and user expectations adapt, so effects will attenuate.
- **Why.** Claiming a small-scale RCT estimate transfers to a full rollout is the classic scaling error, and interviewers probe for it directly.
- **Soundbite.** "These are short-run effects at partial rollout. At scale, couriers reposition, merchants adjust, and users learn to wait for discounts — so I'd expect attenuation, and the persistent holdout is how I'd measure it."

---

### Rollout and lifecycle decisions

**ADR-035 · Staged rollout with a persistent holdout carved before allocation**
- **Decision.** 5% randomized validation → 20% → 50% → 100%, with a permanent 2% never-treated holdout sampled *before* the optimizer runs. Rollback thresholds pre-committed on primary and all five guardrails.
- **Why.** Offline policy value is an estimate under assumptions; the holdout is the only way to measure realized incremental value on an ongoing basis. Sampling it before allocation keeps it a random sample of the eligible population rather than the customers the optimizer declined. Pre-committing thresholds removes the after-the-fact rationalisation that kills bad campaigns too slowly.
- **Consequences.** The holdout costs real value — 2% of eligible customers forgo an offer that is (in expectation) profitable. That cost is quantifiable from the profit curve and should be stated: it is the price of knowing whether the system works.
- **Soundbite.** "The holdout is carved before allocation, not after, so it's a random sample of the eligible population. It costs us about ₹X a quarter in forgone margin, and that's the price of being able to answer 'is this still working' twelve months from now."

**ADR-036 · Explicit retraining triggers, not a fixed cadence alone**
- **Decision.** Retrain on any of: calibration drift (Brier score degradation past threshold), feature drift (PSI > 0.2 on any top-10 feature), holdout-measured lift decay below the lower bound of the launch interval, or 90 days elapsed — whichever fires first.
- **Why.** A pure calendar cadence retrains when nothing changed and misses breakage between cycles.
- **Soundbite.** "Four triggers, any of which fires a retrain. The one people forget is allocation drift — if the share of budget going to a segment moves 20% week over week with no policy change, something upstream broke, and that usually shows up before the outcome metrics do."

**ADR-037 · Three-tier labelling: measured / estimated / simulated**
- **Decision.** Every number in every artifact carries one of three labels, applied consistently in charts, tables, README, and the exec case study.
- **Why.** This project mixes a real RCT, model estimates on held-out data, and a simulator. Conflating them is the most damaging thing I could do to the project's credibility, and being visibly rigorous about it is one of its strongest signals.
- **Soundbite.** "Measured means it came from the randomized experiment. Estimated means it's a model output on held-out data. Simulated means it came from my generator. Every chart says which, and no résumé bullet claims realized business impact."

**ADR-038 · Scope cuts, recorded on purpose**
- **Deliberately not built:** orchestration (Airflow/Dagster), a model registry, deep-learning CATE estimators (DragonNet/TARNet), contextual bandits, dose-response modeling of continuous discount depth, a real-time scoring service, and a full dispatch simulator.
- **Why each.** Orchestration: one weekly DAG, a Makefile is honest. Registry: adds no decision value. Deep CATE: will not beat a cross-fitted DR-learner on 12 anonymised features. Bandits: the right long-term architecture but requires exploration budget, off-policy evaluation infrastructure, and non-stationarity handling — a separate project. Dose-response: needs monotonicity and smoothness constraints on the response curve; genuinely interesting, genuinely out of scope. Real-time serving: the decision is weekly and batch. Dispatch simulator: the extension exists to demonstrate marketplace reasoning, not to become the main project.
- **Why record it.** "What did you decide not to build, and why?" is a senior-level question, and having a written answer signals judgement rather than enthusiasm.
- **Soundbite.** "Bandits are where this goes next, and I can tell you exactly what it would take — an exploration budget, off-policy evaluation you trust, and a story for non-stationarity. That's a second project, not a phase of this one."

---

## 7. Phased plan — decisions, gates, and risks

The build spec has the task checklists. This table adds what the spec leaves out: the decision made in each phase, the risk that phase carries, and the thing an interviewer will actually ask about it.

| Phase | Wk | Core decision made here | Exit gate | Biggest risk | The question you'll get |
|---|---|---|---|---|---|
| **0** Framing | 1 | Objective, estimand, denominator, guardrails (ADR-001,002,008,009,013) | Explain the problem, decision, metric, constraints, and harms with no mention of a model | Vague objective → everything downstream measures the wrong thing | "What's your primary metric and why that denominator?" |
| **1** Data model | 2 | Grain, PK, lifecycle states, what's pre- vs post-treatment (ADR-005) | Every feature provably pre-treatment; every metric has num/denom/grain/window | Building features before declaring the decision timestamp | "How do you know none of your features leak?" |
| **2** SQL layer | 3 | SQL-first, contracts as gate (ADR-010,011,012) | One-command rebuild; all contract tests pass | Silent join fan-out inflating every metric | "Walk me through the point-in-time join." |
| **3** Experiment | 4–5 | ITT, `visit` primary, SRM halt, adjustment as precision only (ADR-014,015,016,017) | Recommendation accounts for uncertainty, effect size, value, guardrails, validity | Reporting a lift without checking SRM first | "The test is flat. What do you do?" |
| **4** Propensity | 6 | Incumbent strawman, calibration mandatory (ADR-018,019) | `P(Y=1\|X)` vs `E[Y(1)−Y(0)\|X]` clearly separated; no predictive metric used as causal evidence | Getting attached to a good AUC | "You have a 0.82 AUC model. Should we send the offer to the top decile?" |
| **5** Estimator validation | 7 | Prove the tools before using them (ADR-020) | Recovers known effects; visibly degrades under poor overlap | Skipping it because it produces no business result | "How do you know your DR estimator is implemented correctly?" |
| **6** HTE | 8–9 | Learner ladder, cross-fitting, policy-value evaluation, null baseline (ADR-021,022,023,024,025) | Beats constant-effect on held-out policy value with uncertainty, **or** honestly reports no reliable heterogeneity | Modeling noise and believing a Qini number | "How do you know the uplift model isn't fitting noise?" |
| **7** Optimization | 10 | MCKP formulation, redeemed cost, λ, matched-budget protocol (ADR-026,027,028,029,030) | Optimizer compared to realistic baselines at matched budgets; headline is a decision metric | Comparing at unmatched budgets; using exposure cost | "How much better is the ILP than just sorting by uplift?" |
| **8** Marketplace | 11 | SUTVA violated, capacity as constraint, geo design (ADR-031,032,033,034) | Explains when customer-level uplift is insufficient because treatment changes conditions for others | Letting it grow into a dispatch simulator | "Your A/B test says +5%. Why won't you get +5% at full rollout?" |
| **9** Rollout | 11 | Staged gates, pre-allocation holdout, retraining triggers (ADR-035,036) | A reader can determine what ramps, pauses, rolls back, retrains | Vague thresholds that can be rationalised away later | "What would make you turn this off?" |
| **10** Packaging | 12 | Labelling discipline, decision-first README (ADR-037,038) | Presentable without opening code; every causal/financial claim traceable to identification → estimator → assumptions → uncertainty | Overclaiming in the résumé bullet | "Which of these numbers is real?" |

### Phase dependency rules (do not violate)
- Phase 3 does not start until the Phase 2 leakage test passes.
- Phase 6 does not start until Phase 5's estimator-recovery benchmark passes.
- Phase 7 does not report a single number until Phase 6 has a policy-value interval.
- Phase 10's résumé bullet is not written until Phase 7's held-out evaluation is complete.

---

## 8. Interview question bank

Organised by the way interviews are actually structured. For the high-value questions I give **what's being tested**, an **answer skeleton**, and the **trap**. The rapid-fire lists at the end of each section are questions you should be able to answer in under 60 seconds.

---

### 8.1 Product sense and problem framing

**Q. Walk me through this project in two minutes.**
- *Testing:* can you lead with the decision instead of the method.
- *Skeleton:* Problem (budget spent with no counterfactual, most of it on customers who'd convert anyway) → decision (who gets which offer under a fixed budget) → approach in four steps (measure, estimate heterogeneity, price it, allocate under constraints) → headline result with its label (estimated, held-out, with an interval) → the one caveat you'd flag first.
- *Trap:* starting with "I used a DR-learner." Never open with a method.

**Q. Why is this a problem worth solving? How would you size it?**
- *Skeleton:* Budget × share going to already-converting customers. If 60% of treated conversions would have happened anyway, that fraction of spend has zero incremental return. Size it as budget × (1 − incrementality rate). Then bound it: even a 10pp improvement in targeting efficiency on a ₹2M quarterly budget is ₹200k of recovered margin per quarter, per market.
- *Trap:* sizing with conversion rates instead of incremental conversion rates.

**Q. Your primary metric is incremental contribution margin per eligible customer. Defend the denominator.**
- *Skeleton:* The decision applies to the eligible population. A per-treated denominator lets a policy win by treating fewer, easier customers, which is exactly the failure mode I'm trying to fix. Per-eligible makes treat-none, treat-all, and optimized directly comparable.
- *Trap:* not noticing the question is about the denominator.

**Q. A PM says "just send the offer to everyone, it's cheap." Respond.**
- *Skeleton:* Three reasons: (1) cannibalisation — you pay for orders you'd have got free; (2) sleeping dogs — some segments respond negatively to contact and you'd need the uplift model to find them; (3) capacity — a demand spike into a supply-constrained city-hour degrades delivery time for everyone, and the guardrail cost is not in the offer budget. Then: "and if all three turn out small, treat-all is genuinely the right answer, which is why it's one of my baselines."
- *Trap:* arguing from model sophistication rather than economics. The best version of this answer concedes that treat-all might win.

**Rapid fire.** Who is the user? Who is the decider? What's the cadence? What's out of scope and why? What would you build if you had one more month? What's the cheapest version of this that captures 80% of the value? How would this change for a subscription business? What if the budget were unlimited?

---

### 8.2 Metrics

**Q. How do you define your guardrails, and how do you set thresholds?**
- *Skeleton:* Each guardrail is a mechanism hypothesis, not a checklist item — cancellation and refund because offer-driven impulse orders behave differently; negative-margin share because a large offer on a small basket is loss-making by construction; p95 delivery time because demand spikes hit shared supply; contact frequency because annoyance is a permanent channel loss, not a temporary one. Thresholds come from historical variation: set them at a level that fires less than ~1% of the time under normal operation, then pre-commit the action.
- *Trap:* listing guardrails without mechanisms, which makes the thresholds arbitrary.

**Q. What's the difference between a guardrail, a secondary metric, and a diagnostic?**
- *Skeleton:* Guardrail: you'd stop the launch if it moves the wrong way, even if the primary is positive. Secondary: informs the interpretation but doesn't gate. Diagnostic: explains *why* the primary moved; never a decision input on its own.

**Rapid fire.** What's the OEC here? Why not GMV? Why not LTV? How would you handle a metric that improves short-term and hurts long-term? What's a ratio metric and why does its variance need special handling? How do you detect a metric definition change breaking a time series?

---

### 8.3 SQL and data engineering

**Q. Explain point-in-time correctness and how you implemented it.**
- *Skeleton:* Each row is (user, decision_ts). Every feature aggregates events with `event_ts < decision_ts`, strict. Implemented with DuckDB `ASOF JOIN`. The regression test shifts `decision_ts` backwards and asserts rolling counts are non-increasing; a feature that grows when the decision moves earlier is leaking.
- *Trap:* saying "I split by date." Date-level joins admit same-day post-decision events.

**Q. You joined orders to users and your user count went up. What happened and how do you catch it in future?**
- *Skeleton:* Fan-out from a non-unique join key. Catch it with a row-count invariance assertion before and after the join, plus a `HAVING COUNT(*) > 1` duplicate check on the join key in the contract layer. In my pipeline this is a build-time gate, not a manual check.

**Q. Write a query for weekly cohort retention.** / **Rolling 30-day margin per user as of an arbitrary timestamp.** / **Second-highest order value per city.**
- Practise these until they're muscle memory. The implemented query patterns are documented in `docs/technical_appendix.md`.

**Rapid fire.** Grain of your fact table? Difference between `RANK`, `DENSE_RANK`, `ROW_NUMBER`? When is a window frame `ROWS` vs `RANGE`? How do you find gaps in a sequence? Why `NOT EXISTS` over `NOT IN`? What breaks when you `LEFT JOIN` then filter on the right table in `WHERE`?

---

### 8.4 Experimentation

**Q. Your test shows +2.1% lift, p = 0.03. Ship it?**
- *Skeleton:* Not yet. In order: (1) SRM check — if assignment is broken, nothing else matters; (2) is 2.1% above the MDE I designed for, or did I get lucky and now face the winner's curse; (3) guardrails — did cancellations or delivery time move; (4) is the confidence interval's *lower* bound still business-positive after offer cost; (5) representativeness — which segments, which weeks, novelty effects; (6) was 2.1% the only metric I looked at, and how many did I look at.
- *Trap:* answering yes or no. The answer is a checklist with a decision at the end.

**Q. What is SRM, why does it matter, and what causes it?**
- *Skeleton:* Observed assignment ratio differs from designed ratio by more than chance; chi-square test, and a threshold like p < 0.001 because you want near-certainty before halting. It matters because it means the assignment or logging mechanism is broken, which invalidates everything downstream regardless of how good the result looks. Causes: bot filtering applied asymmetrically, redirect/latency loss in one arm, triggering-condition bugs, logging differences, and users being removed after assignment. Microsoft found roughly 8% of experiments affected — it's common, not exotic.

**Q. Your treatment and control differ significantly on one covariate. What do you do?**
- *Skeleton:* Report it, don't correct it. With 12 covariates at α = 0.05 you expect roughly one significant imbalance by chance. Investigate whether it's chance or a symptom of broken assignment — check SRM, check the assignment hash, check whether the imbalance is in the randomization unit or an analysis-unit artefact. If randomization is sound, matching or re-weighting would condition on realised chance and break the design-based inference I paid for.
- *Trap:* "I'd use propensity score matching." This single answer will end a serious causal interview.

**Q. Calculate the sample size for a test.**
- *Skeleton:* Baseline rate, MDE, α, power, then `n ≈ 16·σ²/Δ²` per arm as a fast approximation for 80% power / 5% α, or `2(z_{α/2}+z_β)²σ²/Δ²` precisely. State the duration implied by traffic, and the extra cost of a third arm. Then flip it: "at my available traffic, my MDE is X — is X a business-relevant effect? If not, the test isn't worth running."
- *Trap:* computing n and stopping. The valuable move is inverting to MDE and asking whether it's decision-relevant.

**Q. What is CUPED and when would you use it?**
- *Skeleton:* Variance reduction using a pre-experiment covariate correlated with the outcome; subtract off its explained variation. Reduces the SE, which reduces the MDE, which shortens the test. It does not remove bias, because there is no bias in a randomized test. Must be pre-specified so it isn't a specification search.

**Rapid fire.** Type I vs Type II cost in this context? What's the winner's curse? Novelty vs primacy effect? Why is peeking a problem and what fixes it? Randomization unit vs analysis unit? When would you randomize at session level instead of user level? What's an A/A test for? How do you handle multiple metrics?

---

### 8.5 Causal inference

**Q. State the assumptions you need to identify a causal effect and say which randomization gives you.**
- *Skeleton:* Unconfoundedness/ignorability — randomization gives it. Positivity/overlap — randomization gives it, by construction. Consistency (well-defined treatment) — randomization gives it if the treatment is uniform. **SUTVA — randomization does not give it**, and in a marketplace it is the one that fails. Then pivot immediately into the interference story; that pivot is the answer they're hoping for.

**Q. Draw the DAG for your problem. What do you include and exclude?**
- *Skeleton:* Pre-treatment user state → both treatment eligibility and outcome (confounders in the observational world, irrelevant under randomization but useful for precision). Treatment → redemption → outcome: redemption is a **mediator**, so including it as a feature answers a different question and blocks part of the effect. Exposure is post-randomization, so conditioning on it induces collider bias. Nothing post-treatment goes in the feature set.

**Q. Why doesn't a high AUC propensity model tell you who to target?**
- *Skeleton:* `P(Y=1|X)` ranks who converts. `E[Y(1) − Y(0)|X]` ranks who converts *because of* the offer. These are different orderings and can be nearly orthogonal. The customers with the highest conversion probability are frequently sure things — they convert either way, so treating them is pure cost. Concretely: my propensity policy and my uplift policy overlap in only ~X% of the treated set at matched budget, and the margin difference is ₹Y.
- *Trap:* stating the formulas without the business consequence.

**Q. What is a doubly robust estimator and why "doubly"?**
- *Skeleton:* Combines an outcome regression with inverse-propensity weighting such that the estimator is consistent if *either* model is correctly specified. The IPW term corrects the outcome model's bias; the outcome term stabilises the IPW's variance. In the DR-learner, this becomes a pseudo-outcome regressed on X to get the CATE, and it requires cross-fitting because the pseudo-outcome depends on fitted nuisances.

**Q. Someone shows you an observational analysis claiming a promotion caused a 12% lift. How do you evaluate it?**
- *Skeleton:* Ask what determined who got the promotion — if targeting was based on likelihood to convert, the estimate is confounded in the direction of the finding. Check overlap. Ask what's in the adjustment set and whether anything is post-treatment. Ask for a placebo/negative-control outcome. Then the strongest move: point to my own experiment where I induced confounding in randomized data and measured how far the observational estimate drifted from the randomized benchmark — that gives a concrete magnitude rather than a hand-wave.

**Rapid fire.** ATE vs ATT vs CATE? What's a collider and give an example? Why is controlling for a mediator wrong? What does positivity failure do to IPW variance? What's the difference between confounding and selection bias? When is regression adjustment sufficient? What's a negative control outcome?

---

### 8.6 ML and modeling

**Q. Why calibration, and how did you check it?**
- *Skeleton:* Because the value function multiplies a probability by rupees; ranking metrics are blind to systematic overconfidence, and an overconfident model makes the optimizer overspend. Checked with a reliability diagram and Brier score on a held-out fold, calibrated with isotonic regression fit outside the training folds.

**Q. Four kinds of leakage. Name them and say where each could occur here.**
- *Skeleton:* Target leakage (redemption/cancellation features — blocked by the post-treatment source list). Train–test contamination (scaler fit before split — prevented by fitting inside folds). Group leakage (same user in train and test — prevented by user-level fold assignment). Temporal leakage (same-day events after decision_ts — prevented by the strict `<` as-of join and its regression test).

**Q. Why PR-AUC and not just ROC-AUC?**
- *Skeleton:* At a 0.29% positive rate, ROC-AUC is dominated by the enormous negative class and looks good for models that are useless at the operating point. PR-AUC reflects performance where the decisions actually happen.

**Rapid fire.** LightGBM vs logistic regression here, and why keep both? What does `min_data_in_leaf` control? How do you pick a threshold? What's the bias–variance framing of the S- vs T-learner? Why not a neural CATE model?

---

### 8.7 Uplift and policy evaluation

**Q. How do you evaluate an uplift model when you never see the true uplift?**
- *Skeleton:* You don't score the label, you score the *policy*. Three layers: (1) uplift-by-decile on held-out randomized data — actual treated-minus-control within each predicted-uplift decile, which should decrease monotonically; (2) Qini/AUUC against a random-ranking null with bootstrap bands; (3) doubly robust policy value, which is the decision metric and the only one I'd quote.
- *Trap:* mentioning AUC at all.

**Q. How do you know your uplift model isn't fitting noise?**
- *Skeleton:* Four checks. (1) Random-ranking null through the identical evaluation pipeline — if my interval overlaps it, I have nothing. (2) Stability across seeds and across pre-treatment segments. (3) The constant-effect policy as a floor — a sophisticated learner that can't beat "one ATE for everyone" hasn't found heterogeneity. (4) Simulation: my learners recover known τ on a DGP where I control the truth, so I know the implementation is sound and any failure on real data is a signal problem, not a code problem.

**Q. Explain the Qini curve to a marketing director.**
- *Skeleton:* "Sort customers by how much we think the offer will change their behaviour, best first. Walk down that list. The curve shows the extra orders we've gained by the time we've contacted that many people. A straight diagonal is what random targeting gets. The higher the curve bows above the diagonal, the more the model is finding people who genuinely respond."

**Q. What are persuadables and sleeping dogs, and how confident are you in the labels?**
- *Skeleton:* They're the four cells of a 2×2 over potential outcomes, and they are **latent** — I never observe which cell a customer is in. What I have is a model's estimate, so I say "top decile of estimated uplift", not "this customer is a persuadable." Sleeping dogs are especially fragile: negative uplift estimates are the noisiest region of the model, and I'd want a dedicated experiment before I acted on one.

**Rapid fire.** Qini vs AUUC? What does a normalized AUUC of 0.5 mean? Why is the S-learner biased toward zero effect? Why does X-learner help under 85/15 imbalance? What is cross-fitting protecting against? What's the difference between IPW and DR policy value?

---

### 8.8 Optimization

**Q. Why is this an optimization problem and not just a ranking?**
- *Skeleton:* With one budget and one action, ranking by value-per-rupee is essentially optimal, and I show that — greedy comes within a fraction of a percent. It stops being a ranking the moment you add (a) multiple actions with an exactly-one constraint, (b) a contact-volume cap that binds before the budget does, (c) per-segment frequency caps, and (d) city-hour capacity, because those constraints couple customers to each other. Coupled constraints are what a solver is for.
- *Trap:* overclaiming the optimizer's advantage. The strong answer concedes greedy is close on the simple case.

**Q. What is the shadow price and why do you report it?**
- *Skeleton:* The Lagrange multiplier on the budget constraint: the incremental margin generated by the next rupee. It answers a question the allocation cannot — "should we ask Finance for more budget?" You fund up to the point where λ falls to 1, and the profit-vs-budget curve is just λ integrated. It's also how the optimizer scales: fix λ and the problem decomposes into an independent per-customer threshold rule.

**Q. Ten million customers, three actions. How do you solve it?**
- *Skeleton:* Not with 30M binaries in a MIP. Lagrangian relaxation on the budget: bisect on λ, and at each λ every customer's choice is independent (pick the action maximising `v(i,a) − λ·c(i,a)`), so it's O(n) per iteration. Recover integrality trivially — at most one customer is fractional. Keep the full ILP for the small instance where you need coupling constraints and use it as a correctness check. If the coupled constraints (capacity, segment caps) are essential at scale, bucket customers into cells and solve at cell level.

**Rapid fire.** Multiple-choice knapsack vs 0/1 knapsack? When does LP relaxation give an integral solution? What's a MIP gap? CP-SAT vs a MIP solver? What happens if two constraints are jointly infeasible, and what do you do about it? How do you handle uncertainty in `v(i,a)` when optimizing?

**Q. Your τ̂ is noisy. Doesn't the optimizer just pick the customers with the largest estimation errors?**
- *Testing:* whether you know about the optimizer's winner's curse. This is the sharpest question in this section.
- *Skeleton:* Yes, that's a real bias — maximising over noisy estimates selects for upward error, so realized value is systematically below the optimizer's projection. Three mitigations: (1) shrink τ̂ toward the ATE (empirical-Bayes style), which is exactly what the constant-effect baseline is a limiting case of; (2) allocate on decile-level or cell-level averaged uplift rather than raw individual scores, trading resolution for stability; (3) evaluate the *policy* on held-out data rather than reading the optimizer's own objective, which is what I do — the gap between projected and held-out policy value is the size of the problem, and I report it.

---

### 8.9 Marketplace and interference

**Q. Your user-level test says +5%. Will you get +5% at full rollout?**
- *Skeleton:* Almost certainly not, and probably less. Three reasons: (1) **interference** — treating a user consumes shared courier capacity, so the control group's outcomes were depressed by the treatment group, which inflates the measured gap; with congested supply, user-level tests overstate demand-stimulating treatments; (2) **equilibrium** — at scale, couriers reposition, merchants adjust, and users learn to expect discounts; (3) **selection into the estimate** — the policy was optimized on the same distribution I evaluated it on. The way to find out is a geo experiment, and that's what Phase 8 designs.

**Q. Design an experiment that handles interference here.**
- *Skeleton:* Identify the interference channel first — here it's local supply, so it's geographic. Cluster-randomize cities (or delivery zones), analyse with cluster-robust SEs, accept the power hit and quantify it. Then the comparison: switchback handles simultaneous interference but carries carryover risk, which is bad for promotions specifically because their effect persists past the window; budget-split is arguably better for a spend-mediated treatment and DoorDash reports substantially better MDEs, but it needs platform support. Say which you'd choose and what would change your mind.

**Q. Your geo test only has 40 clusters. Is that enough?**
- *Skeleton:* Probably not for small effects — state the MDE. Then the options: stratify clusters on pre-period volume to reduce variance, extend duration, use a synthetic-control or difference-in-differences analysis to exploit pre-period data, or switch to budget-split which recovers power by removing the cluster structure entirely. The honest answer includes "and if none of those get me to a decision-relevant MDE, I'd say so rather than run an underpowered test and interpret the noise."

**Rapid fire.** What exactly does SUTVA say? Which direction does interference bias the estimate here, and why? What's a carryover effect? Why do switchback experiments have low power? What's a spillover vs a network effect? How would you detect interference empirically?

---

### 8.10 Rollout, monitoring, and lifecycle

**Q. What would make you turn this off?**
- *Skeleton:* Pre-committed thresholds, not judgement calls. Primary: holdout-measured incremental margin below the launch interval's lower bound for two consecutive weeks. Guardrails: cancellation or refund rate above threshold; p95 delivery time breach in more than N city-hours; contact frequency violation of any kind (immediate, no threshold — it's a policy breach). Operational: budget overrun, or allocation-mix drift beyond 20% week over week without a policy change.

**Q. How do you measure realized impact after launch?**
- *Skeleton:* The persistent 2% holdout, carved before allocation so it's a random sample of the eligible population rather than the customers the optimizer declined. Compare realized incremental margin per eligible customer, holdout vs treated population, on a rolling 14-day closed window. This is also the only clean way to detect model decay, since predictive metrics can look fine while the policy stops adding value.

**Q. Offline you projected +18%. Online you got +7%. What happened?**
- *Testing:* whether you have a diagnostic framework, not an excuse.
- *Skeleton:* Decompose the gap. (1) Optimizer winner's curse — maximising over noisy τ̂ overstates. (2) Interference — offline evaluation assumed SUTVA. (3) Distribution shift between the evaluation window and the live population. (4) Implementation drift — did the sends actually match the allocation? Check delivery rates first, it's the most common and least interesting cause. (5) Outcome-window truncation if you read early. Rank them by how much of the gap each could explain and test the cheapest one first.

**Rapid fire.** Why not retrain weekly? What's PSI and what threshold? What's calibration drift and how is it different from feature drift? What's allocation drift and why is it an early warning? How do you handle delayed conversions in monitoring? What does the holdout cost you and how would you compute that?

---

### 8.11 Executive and consulting-style

**Q. You have 60 seconds with the CFO. Go.**
- *Skeleton:* "We're spending ₹2M a quarter on promotions and we can't currently say what it bought, because most of the orders we count would have happened anyway. I built a system that measures the incremental effect with a randomized test, estimates which customers actually respond, and allocates the budget to maximise incremental margin under the budget and capacity constraints we already have. On held-out data it delivers about [X]% more incremental margin than our current approach at the same spend, and it tells you the marginal return of the next rupee so you know when to stop funding it. I'd validate it with a 5% rollout against a permanent holdout before scaling."

**Q. How would you structure this as a consulting engagement?**
- *Skeleton:* Issue tree. Root: "Is our promotional spend generating incremental margin?" Branch 1: are we measuring incrementality at all (no counterfactual → the whole readout is unreliable). Branch 2: are we targeting the right customers (propensity ≠ uplift). Branch 3: are we choosing the right offer depth (small vs large trade-off). Branch 4: are we constrained by something other than budget (capacity, frequency policy). Each branch has a hypothesis, a test, and a data requirement. Then MECE the recommendation: quick win (stop treating the top propensity decile), medium (uplift-based allocation), structural (capacity-aware optimizer with a permanent holdout).

**Q. The client's head of marketing disagrees with your recommendation. How do you handle it?**
- *Skeleton:* Find out whether the disagreement is about the evidence, the assumptions, or the consequences. If evidence — walk through the matched-budget comparison and the interval. If assumptions — the assumptions register exists precisely for this; re-run the headline at their numbers and see if the recommendation flips. If consequences (they own a KPI my recommendation hurts) — that's a real conflict, and the honest move is to surface the trade-off explicitly to the decision-maker rather than argue it in private.

**Rapid fire.** What's your recommendation in one sentence? What are the three biggest risks? What would you need to believe for this to be wrong? What's the cheapest way to test the riskiest assumption? How would you sequence this over two quarters? What's the org change required, not just the model?

---

### 8.12 Stress questions (rehearse these hardest)

**Q. What's the weakest part of this project?**
- The strongest answer is specific and unprompted. Pick your real one. Candidates: the multi-action results rest on simulated data because Criteo's treatment is binary; the margin and redemption assumptions drive the economics more than the model does; the bootstrap doesn't capture model-selection uncertainty; the marketplace extension is a simulation with a DGP I chose, so it demonstrates reasoning rather than measures anything.

**Q. What did you get wrong the first time?**
- Have two real answers ready with what you changed. If you genuinely got nothing wrong, you didn't build it.

**Q. What did you decide *not* to build?**
- ADR-038, said conversationally. This is a seniority question.

**Q. If the uplift model didn't beat treat-all, was the project a failure?**
- *Skeleton:* No — it would mean the effect is roughly homogeneous, which is itself a decision-relevant finding: it says stop investing in targeting sophistication and start investing in offer design or in expanding the eligible population. The project's value is the decision framework and the measurement discipline; the specific heterogeneity result is an empirical outcome that could legitimately go either way. Then: "and here's what I'd need to see to change my mind — a segment where the interval separates from the ATE."

**Q. This is a portfolio project. Why should I believe any of these numbers?**
- *Skeleton:* You shouldn't believe the business numbers, and I don't present them as realized impact — they're labelled estimated or simulated everywhere. What you should evaluate is whether the *method* would give a trustworthy answer on real data. Three pieces of evidence: my inference code is calibrated (A/A histogram is uniform), my estimators recover known effects and visibly fail under poor overlap, and my policy evaluation includes a random-ranking null. Those are the things that transfer.

---

## 9. Failure modes and how to present them

Every one of these is a plausible outcome. None of them makes the project worse if you handle it correctly. What makes a project worse is pretending it didn't happen.

| Outcome | Wrong response | Right response |
|---|---|---|
| Uplift model doesn't beat the constant-effect baseline | Tune until the Qini goes up | "No reliable heterogeneity was established on this data at this sample size. Here's the null baseline, here's the interval, and here's what that implies: invest in offer design and eligibility, not targeting sophistication." |
| Optimizer beats greedy by only 0.4% | Bury the greedy comparison | "The optimizer's value shows up when constraints couple customers. On a single budget constraint, sorting by value-per-rupee is essentially optimal, and I show that. Capacity and frequency caps are where the solver earns its keep." |
| ATE is small but statistically significant | Report the relative lift and hope | "The effect is real and small. At my offer cost, the lower bound of the interval implies a negative ROI, so my recommendation is don't ship at this offer depth — and here's the offer depth at which it turns positive." |
| Guardrail trips in the simulated rollout | Remove the guardrail | "This is the mechanism I predicted in Phase 0 and it fired. Here's the capacity-aware policy that avoids it and what it costs in headline margin." |
| Wide bootstrap intervals | Report the point estimate only | "The interval is wide because uplift is a low-signal problem at this sample size. Here's the sample size I'd need to halve it, and here's whether that's worth the cost." |
| Sleeping-dog (negative uplift) segment looks real | Act on it | "Negative uplift estimates are the noisiest part of the model. Before suppressing contact for that segment, I'd run a dedicated experiment — the estimate is suggestive, not actionable." |

**The framing that makes all of these land:** you separate *the method being sound* from *the empirical result being positive*. A project where the method is airtight and the result is modest is a strong project. A project with a spectacular result and no null baseline is a weak one, and experienced interviewers know which is which within about three questions.

---

## 10. The presentation

### 10.1 Ten-minute structure
| Min | Content | Artifact |
|---|---|---|
| 0–1 | Situation + complication: budget spent, no counterfactual, most of it cannibalised | one slide, no charts |
| 1–2 | The decision and the metric tree | `metric_tree.png` |
| 2–3.5 | The randomized experiment: ATE with interval, SRM and validity checks | experiment readout |
| 3.5–4.5 | Why propensity targeting wastes budget | the 2×2, propensity-vs-uplift overlap number |
| 4.5–6 | Heterogeneity: uplift deciles, Qini vs the random null | `uplift_deciles.png`, `qini_comparison.png` |
| 6–7.5 | **The result:** profit vs budget, all policies, matched constraint, with bands | `profit_vs_budget.png` |
| 7.5–8.5 | Shadow price: how much budget should we actually ask for | `shadow_price_curve.png` |
| 8.5–9.5 | Why customer-level uplift isn't enough: capacity and interference | `capacity_aware_vs_naive.png` |
| 9.5–10 | Rollout, holdout, rollback, and the three things I'd flag as risks | rollout decision table |

Rehearse until you can drop slides 8 and 9 without losing the thread — technical interviewers will interrupt and you will run out of time.

### 10.2 Two-minute version
Problem → decision → four steps → headline number with its label and interval → the one caveat you'd raise yourself.

### 10.3 Thirty-second version
"I built a system that decides who gets a promotional offer under a fixed budget. It measures incrementality from a randomized experiment, models which customers actually respond, converts that into expected margin net of offer cost, and allocates the budget as a constrained knapsack — including a marketplace capacity constraint, because a policy that's optimal per customer can overload local supply. On held-out data it's [X]% better than the current approach at the same spend, and it reports the marginal return of the next rupee so Finance knows when to stop."

---

## 11. Positioning by role

The same project, three different emphases. Know which one you're in before you open your mouth.

| | **MBB / consulting analytics** | **Product DS (Eternal, Uber-style)** | **Marketplace / causal DS** |
|---|---|---|---|
| Lead with | Business framing, issue tree, recommendation and its risks | Metric definition, experiment design, ship/no-ship judgement | Identification, interference, estimator validity |
| Emphasise | Profit-vs-budget curve, shadow price, sensitivity to assumptions, org implications | Metric tree, guardrails, propensity-vs-uplift, rollout gates and holdout | Phase 5 estimator recovery, cross-fitting, policy value, geo design |
| Have ready | Mental math on sizing, a MECE structure, a one-page exec summary | "How would you test X" for any product they name | The DAG, the four assumptions, the SUTVA pivot |
| Downplay | Solver internals, cross-fitting mechanics | Optimization theory | Dashboard, packaging |
| The failure mode | Sounding like a modeller who found a business problem | Sounding like a researcher who won't ship | Sounding like a practitioner who hasn't checked their assumptions |

### Résumé bullets (fill only after Phase 7's held-out evaluation is complete)

**Primary:**
> Built an end-to-end incentive allocation engine on a 14M-row randomized advertising experiment: point-in-time SQL feature layer, ITT effect estimation with SRM/balance diagnostics, cross-fitted DR-learner for heterogeneous treatment effects, and a multiple-choice-knapsack allocator under budget, contact, and marketplace-capacity constraints. Improved **estimated** incremental contribution margin by **[X]%** over the propensity-targeting baseline at a matched budget, with bootstrap intervals and a capacity-aware geo-randomized rollout design.

**Shorter, for a one-page CV:**
> Incentive allocation engine: randomized-experiment measurement → cross-fitted uplift models → budget-constrained ILP allocation. **[X]%** higher estimated incremental margin than propensity targeting at matched budget, with uncertainty quantification and a staged rollout plan.

**Rules for the number.** It comes from held-out doubly robust policy value, not from the optimizer's own objective. It is always described as *estimated* or *simulated*. It is compared against a **named** baseline at a **matched** budget. If the bootstrap interval crosses zero, there is no number — you describe the finding instead. Nobody has ever been penalised for a résumé bullet that says "established that treatment effects were approximately homogeneous, and quantified the ceiling on targeting value."

---

## 12. Definition of done

The project is finished when all twelve are true.

1. `make build && make test` runs green from a clean clone with the small example dataset.
2. The leakage test exists and fails when you deliberately break the as-of join.
3. The A/A p-value histogram is uniform.
4. The estimator-recovery benchmark shows correct coverage under valid assumptions and visible degradation under poor overlap.
5. The uplift evaluation includes a random-ranking null with bootstrap bands.
6. Every policy comparison is at a matched budget on the same eligible population.
7. The headline number is a decision metric with an interval, not a model metric.
8. Every chart labels its content as measured, estimated, or simulated.
9. `docs/rollout_plan.md` answers ramp / pause / roll back / retrain without further explanation.
10. The README states the decision and the result before it mentions Python.
11. The decision log's *Consequences* fields describe what actually happened, including at least two things that went differently than planned.
12. You can present the whole thing for ten minutes without opening the code, and trace any causal or financial claim back to its identification strategy, estimator, assumptions, and uncertainty.
