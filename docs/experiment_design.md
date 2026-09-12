# Multi-arm experiment design

The existing Criteo analysis is a binary randomized advertising experiment. It
identifies the intent-to-treat effect of assignment and is the measured causal
anchor. It cannot identify separate small- and large-offer effects.

For the marketplace follow-up, eligible users are randomized once before any
allocation into `no_offer`, `small_offer`, or `large_offer`, with a persistent
control holdout. The primary endpoint is 14-day incremental contribution margin
per eligible customer; conversion, repeat purchase, AOV, cancellation, refund,
delivery time, and contact frequency are secondary or guardrail metrics.

The allocation ratio is selected from the MDE calculation and expected costs,
not tuned after looking at outcomes. SRM, assignment integrity, and incomplete
outcome windows are reviewed before any ramp decision.
