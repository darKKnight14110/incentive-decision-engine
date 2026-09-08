# M2 data dictionary

The synthetic marketplace is generated for pipeline development. It is not a
measured business dataset. Event timestamps are retained so later SQL can apply
strict point-in-time filters.

| Table | Grain | Primary key | Timing role | Important relationships |
|---|---|---|---|---|
| `users` | One row per user | `user_id` | Signup and pre-treatment attributes | Parent of user events |
| `merchants` | One row per merchant | `merchant_id` | Catalogue and operational attributes | Referenced by orders |
| `offers` | One row per offer definition | `offer_id` | Offer catalogue | Referenced by exposures and redemptions |
| `sessions` | One row per user session | `session_id` | Session, cart, and checkout event timestamps | `user_id` references users |
| `orders` | One row per order | `order_id` | Order and completion timestamps | References users and merchants |
| `exposures` | One row per promotional send | `exposure_id` | Treatment/contact event | References users and offers |
| `redemptions` | One row per redeemed offer | `redemption_id` | Post-exposure outcome | References exposures, users, and optional order |
| `cancellations` | One row per cancelled order | `cancellation_id` | Post-order outcome | References orders and users |
| `refunds` | One row per refund event | `refund_id` | Post-order outcome | References orders and users |
| `experiment_assignments` | One row per user-experiment assignment | `assignment_id`; logical key `user_id, experiment_id` | Treatment assignment | References users |
| `city_hour_capacity` | One row per city and hour | `city_id, hour_ts` | Operational capacity context | Used for later marketplace constraints |

## Synthetic data-generating process

- User engagement is sampled from a beta distribution and drives session and
  order intensity, creating realistic correlation rather than independent
  columns.
- Sessions progress through cart and checkout with conditional probabilities.
- Orders select merchants within the user's city and derive variable cost from
  merchant cost rates plus noise. A small set of orders is forced negative-margin
  to exercise guardrails.
- Promotional exposures choose small or large offers. Redemptions sample from
  the configured expected redemption rate and occur after exposure.
- Experiment assignments use fixed arm probabilities and a single decision
  timestamp. Approximately 0.3% duplicate assignment rows are appended by
  design.
- A small number of orders is assigned `order_ts < signup_ts` by design. This is
  an intentionally impossible timestamp that M4 validation must reject.
- Every generator uses an explicit NumPy seed. `manifest.json` records the seed,
  population size, observation window, and row counts when files are written.

The assignment duplicates and impossible order timestamps are raw-data defects,
not corrected business facts. They must be detected and reported before the
analytical layer is built.
