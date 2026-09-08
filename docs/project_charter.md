# Project charter

## Business problem

A marketplace spends a fixed promotion budget but cannot distinguish orders caused by an offer from orders that would have occurred anyway. Counting treated conversions overstates value, subsidizes sure-thing customers, and can hide harm from repeated contact or overloaded local supply.

## Decision statement

Each week, the Growth/CRM lead chooses which eligible customers receive no offer, a small offer, or a large offer. Finance sets the budget and Operations sets capacity limits. The choice changes only when a matched-budget comparison shows a credible improvement in incremental contribution margin per eligible customer and all pre-specified guardrails remain acceptable. Until an online randomized rollout measures realized impact, outputs are described as offline estimates or simulated projections.

## Decision contract

| Item | Definition |
|---|---|
| Decision unit | One eligible customer at one `decision_ts` |
| Cadence | Weekly |
| Decision timestamp | Monday 00:00 UTC for the synthetic weekly cycle |
| Actions | `no_offer`, `small_offer`, `large_offer` |
| Outcome window | `[decision_ts, decision_ts + 14 days)` |
| Attribution | Decision-anchored intent-to-treat; assignment remains in the denominator regardless of exposure or redemption |
| Primary objective | Incremental contribution margin per eligible customer |
| Comparator | The same eligible population under no offer; policy comparisons use matched budgets and constraints |

## Eligibility

Eligibility is a hard rule layer evaluated before scoring. A customer must have a prior completed order, an account at least 7 days old, an active city, contact consent, no suppression, and no promotional contact in the prior 14 days. All conditions are evaluated strictly before `decision_ts`. Legal and contractual rules cannot be traded against expected value.

## Ownership and constraints

- Growth/CRM owns the objective and offer catalogue.
- Finance owns the budget and approves economic assumptions.
- Operations owns city-hour capacity and service thresholds.
- Legal/Trust owns consent, suppression, and contact-frequency policy.
- Data Science owns identification, uncertainty, reproducibility, and result labels.

## Harm hypotheses

| Harm | Mechanism | Control |
|---|---|---|
| Cancellation | Offers induce low-intent impulse orders | Cancellation-rate guardrail |
| Refund | Incentivized purchases have weaker intent or fit | Refund-rate guardrail |
| Margin loss | Deep offers fund low-value or sure-thing orders | Negative-margin-order guardrail |
| Slower delivery | Incremental demand exceeds shared city-hour supply | p95 delivery-time guardrail and later capacity constraint |
| Channel fatigue | Repeated contact causes annoyance and opt-out | Hard 14-day contact cooldown |

## Scope and Phase 0 gate

This is an incentive-allocation decision engine, not a churn model, recommender, pricing engine, bidder, or dispatch simulator. Criteo is randomized advertising data; synthetic marketplace data supplies business plumbing. They are not joined.

M0 passes when the problem, owner, action set, eligible population, primary metric, constraints, evidence threshold, and harm mechanisms can be explained without referring to a model.
