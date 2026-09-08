# M1 learning and build record: unit economics

## Decision contract

The allocation decision is evaluated on expected incremental contribution
margin per eligible customer. A high treated conversion rate is not enough:
the campaign can destroy value when it mostly subsidizes orders that would have
happened anyway, or when the offer cost exceeds the margin from incremental
orders.

## Implemented arithmetic

For customer `i` and action `a`, the value contract is:

```text
value(i, a) = incremental_conversion(i, a)
              * expected_contribution_margin(i)
              - expected_offer_cost(i, a)
```

The expected offer cost has an explicit accounting mode in
`configs/base.yaml`:

```text
exposure   = face_value
redemption = face_value * redemption_rate
```

The implementation lives in `src/economics/unit_economics.py`. It also defines
cost per incremental order and ROI. Efficiency metrics return `None` when the
incremental-order or cost denominator is non-positive instead of reporting a
misleading number.

## Assumptions and boundaries

- Contribution margin excludes fixed platform costs and represents variable
  contribution available to the incremental decision.
- Redemption is an expected cost input, not an observed causal effect by itself.
- Incremental conversion is a counterfactual effect estimate supplied by later
  experiment or causal-policy code; it is not treated conversion rate.
- Base economics remain simulated placeholders and must be sensitivity-tested
  before any business recommendation.

## Verification

`tests/test_unit_economics.py` covers exposure versus redemption accounting, the
three-term value formula, CPIO and ROI denominator guards, and the named config
mode.
