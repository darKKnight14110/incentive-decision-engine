# M0 learning record

## Working definitions

- The OEC is the decision scorecard: incremental contribution margin per eligible customer.
- Drivers explain its movement: incremental orders, margin per order, and redeemed-offer cost.
- Guardrails encode hypothesized harms and can stop a positive-looking decision.
- Diagnostics explain execution but do not prove value.
- Metric names are data contracts. Numerator, denominator, grain, window, and filter must be stable or versioned.

## Checkpoint answers

**Decision without model language.** Each week Growth chooses no, small, or large offer for each eligible customer under Finance's budget and Operations' capacity limits. The choice is justified only if a matched-budget comparison improves incremental contribution margin per eligible customer without unacceptable harm.

**Metric tree.** The OEC decomposes into incremental completed orders, contribution margin per completed order, and expected redeemed-offer cost. See `docs/metric_definition.md` and the generated figure.

**Three harm mechanisms.** A deep offer can turn a small basket margin-negative; a demand spike can overload shared delivery capacity and raise p95 delivery time; repeated contact can cause opt-out and permanently reduce channel reach.

M0 is complete when these answers can be explained from the contract and the automated checks keep action names, windows, assumptions, and policy constraints aligned.
