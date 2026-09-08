# Metric definition and measurement contract

Every metric is a contract with five required fields: numerator, denominator, grain, window, and filter.

## Roles

- **Goal/OEC:** the decision scorecard.
- **Driver:** a causal or economic component of the OEC.
- **Secondary:** a useful outcome that cannot determine the decision alone.
- **Guardrail:** a pre-specified harm signal that can block or reverse launch.
- **Diagnostic:** explains execution or mechanism but does not prove value.

## Metric tree

```text
Incremental contribution margin / eligible customer [OEC]
├── Incremental completed-order rate
│   ├── Baseline order probability [diagnostic]
│   └── Treatment responsiveness [causal driver]
├── Contribution margin / completed order
│   ├── Average order value
│   ├── Variable costs
│   └── Cancellation and refund drag
└── Expected redeemed-offer cost
    ├── Offer face value
    ├── Redemption probability
    └── Cannibalization on orders that would occur anyway
```

## Metric register

| Metric | Role | Numerator | Denominator | Grain | Window | Filter |
|---|---|---|---|---|---|---|
| Incremental contribution margin per eligible customer | Goal/OEC | Margin net of redeemed offer cost under policy minus under no offer | All eligible customers assigned at `decision_ts` | Customer-decision | Closed 14d | Eligibility fixed pre-assignment; ITT |
| Incremental completed-order rate | Driver | Completed-order users under treatment minus expected under control | Eligible customers per arm | Customer-decision | Closed 14d | First qualifying order; ITT |
| Contribution margin per completed order | Driver | Revenue minus variable costs, losses, and redeemed offer cost | Completed orders | Order | 14d | Valid non-test orders |
| Conversion rate | Secondary | Customers with at least one completed order | Eligible customers | Customer-decision | 14d | ITT |
| Repeat-purchase rate | Secondary | Customers with at least two completed orders | Eligible customers | Customer-decision | 28d | Closed window; separate from OEC |
| Average order value | Secondary | Gross order value | Completed orders | Order | 14d | Exclude cancellations |
| Cost per incremental order | Efficiency | Redeemed offer cost | Estimated incremental completed orders | Campaign | 14d | Suppress if denominator non-positive; report interval |
| Cancellation rate | Guardrail | Cancelled orders | Placed orders | Order | 14d | Valid non-test orders |
| Refund rate | Guardrail | Refunded completed orders | Completed orders | Order | 14d | Refund observed in declared window |
| Negative-margin order share | Guardrail | Completed orders with margin below zero | Completed orders | Order | 14d | Include redeemed offer cost |
| p95 delivery time | Guardrail | Empirical 95th percentile delivery minutes | Not a ratio | City-hour | Daily and 14d | Delivered orders; disclose minimum cell size |
| Contacts per customer per 14d | Guardrail | Delivered promotional contacts | Eligible customer | Customer-window | Rolling 14d | All campaign channels |
| Budget utilization | Diagnostic | Redeemed offer cost | Approved budget | Campaign | Cycle | Eligible assignments only |

## Denominator choice

The policy acts on every eligible customer, including those assigned no offer. A per-treated denominator changes when a policy becomes more selective and rewards treating only easy cases. The eligible-customer denominator fixes the decision population and avoids selecting on exposure, redemption, or other post-treatment behavior.

## Reporting labels

| Label | Permitted use |
|---|---|
| **Measured** | Directly observed randomized outcomes or operational facts |
| **Estimated** | Counterfactual effects and policy values |
| **Simulated** | Synthetic events, assumed economics, or projections using them |

Mixed-source outputs take the weakest label and explain their components. Criteo and synthetic marketplace rows are never joined. Early reads are labelled incomplete until the window closes. No predictive metric is evidence of incrementality; policy comparisons use the same population and matched budget.
