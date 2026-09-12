# Rollout and monitoring plan

1. Carve a 2% persistent randomized holdout before allocation.
2. Launch a 5% validation slice. Advance to 20%, 50%, then full ramp only when
   the primary lower confidence bound is non-negative and all guardrails pass.
3. Pause when realized incremental margin is below zero after the outcome
   window closes. Roll back immediately for cancellation, refund, delivery-time,
   or contact-frequency threshold breaches.
4. Retrain when PSI exceeds 0.20, calibration Brier error worsens by 20%, or
   policy mix shifts by 25%. Keep delayed outcomes marked incomplete until the
   full 14-day window is available.

Expected offline value and experimentally realized value are reported in
separate columns and never combined into one business-impact claim.
