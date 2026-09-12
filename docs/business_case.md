# Synthetic marketplace business case

This document is the business-facing interpretation of the checked-in
decision artifact. It is intentionally separate from the Criteo experiment:
Criteo supplies randomized advertising outcomes, while this scenario supplies
multi-action marketplace economics and capacity.

## Headline decision

At the canonical budget of 50% of treat-all-small-offer spend, the
capacity-aware optimizer selects one action per customer and respects both a
50% contact-volume limit and city-hour incremental-demand limits.

| Policy | Expected net contribution | Spend | Treatment rate |
| --- | ---: | ---: | ---: |
| Random | ₹723 | ₹785 | 26.8% |
| Propensity | ₹1,491 | ₹785 | 26.8% |
| Uplift | ₹1,142 | ₹783 | 16.8% |
| Net value | ₹1,142 | ₹783 | 16.8% |
| Capacity-aware optimized | **₹2,038** | **₹788** | **50.0%** |

The optimized-minus-random difference is **₹1,315 in aggregate**, or **₹5.26
per eligible user**. A user-level bootstrap with 500 fixed-policy resamples
gives a 95% interval of **₹4.18 to ₹6.47 per user**. The interval is uncertainty
under this deterministic scenario, not a confidence interval for a live
marketplace.

## Assumptions

All scenario inputs are versioned in [`configs/economics.yaml`](../configs/economics.yaml):

- ₹520 contribution margin per incremental order.
- Small offer: ₹18 face value and 35% redemption.
- Large offer: ₹35 face value and 55% redemption.
- Maximum contact volume of 50% of eligible users.
- City-hour capacity equal to 28% of positive modeled demand, with a minimum
  floor of four incremental orders per city-hour.

These values are placeholders for finance-approved estimates. They are not
derived from Criteo and must not be presented as company financials.

## Why this is useful

The result demonstrates the full business decision loop: response estimates
become expected contribution margin, actions compete for a scarce budget, and
the customer-level optimum is changed by operational capacity. It also creates
an explicit falsification path. If a geo-randomized pilot does not confirm
incremental response, redemption, margin, and delivery guardrails, the policy
should not advance regardless of modeled value.

## Validation plan before launch

1. Re-estimate action-level response with assignment as treatment and a
   pre-treatment feature contract.
2. Validate redemption, contribution margin, cancellation, refund, and
   delivery-time assumptions with finance and operations.
3. Run the cluster-randomized geo design in
   [`docs/geo_experiment_memo.md`](geo_experiment_memo.md), keeping a persistent
   holdout and pre-registering the 50% budget comparison.
4. Compare realized versus expected contribution margin after the full delayed
   outcome window. Pause or roll back on the thresholds in
   [`docs/rollout_plan.md`](rollout_plan.md).

## Sensitivity check

The pipeline also evaluates margin multipliers of 75%, 100%, and 125% and
capacity equal to 20%, 28%, and 40% of positive modeled demand. The optimizer's
advantage is reported for every cell in
[`reports/business_case_sensitivity.csv`](../reports/business_case_sensitivity.csv)
and visualized in `reports/figures/business_case_sensitivity.png`. This guards
against making the headline depend on one favorable assumption grid; the
scenario remains illustrative even where the advantage is positive.
