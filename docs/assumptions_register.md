# Assumptions register

These are design placeholders, not company facts. Machine-readable values live in `configs/base.yaml`.

| ID | Assumption | Base | Source/status | Sensitivity | Risk and validation |
|---|---|---:|---|---|---|
| A01 | Contribution margin rate before offer cost | 22% | Project placeholder | 15% to 30% | Can reverse offer profitability; replace with Finance ledger and rerun bounds |
| A02 | Average order value | INR 800 | Synthetic placeholder | INR 600 to 1,000 | Use the pre-period cohort distribution, not only a mean |
| A03 | Small-offer redemption given assignment | 35% | Synthetic placeholder | 20% to 50% | Estimate by randomized arm; keep outcome analysis ITT |
| A04 | Large-offer redemption given assignment | 55% | Synthetic placeholder | 35% to 70% | Cross with margin sensitivity; never treat redemption as known |
| A05 | Offer face values | INR 50 / 100 | Illustrative catalogue | Campaign-specific | Configure per campaign; do not hard-code in analysis |
| A06 | No customer interference | SUTVA approximation | Unverified and weak under constrained supply | No interference to binding-capacity stress case | Monitor city-hour load and validate via cluster/geo experiment |
| A07 | Decision-relevant effect is captured | 14 days | Design choice | 7, 14, 30 days | Plot cumulative lag; label early reads incomplete |
| A08 | Attribution is assignment-based | ITT | Experiment contract | Descriptive exposure/redemption only | Preserve assignment denominator; redemption is post-treatment |
| A09 | Eligibility is fixed before scoring | Policy config | Governance contract | Exclusion waterfall | Version rules and compare the identical population |
| A10 | Cancellation/refund losses mature in window | 14 days | Unverified | 14 and 28 days | Track maturity curve and extend closed window if material |

The first numerical sensitivity grid crosses contribution margin rate with action-specific redemption. Interference and delayed outcomes need diagnostics or experiment design, not only numerical ranges.
