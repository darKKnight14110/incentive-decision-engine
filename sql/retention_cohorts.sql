-- Signup cohort retention.
-- Grain: one row per signup cohort week and weeks_since_signup.

CREATE OR REPLACE VIEW retention_cohorts AS
WITH signup_cohorts AS (
    SELECT user_id, date_trunc('week', signup_ts) AS cohort_week
    FROM users
), cohort_sizes AS (
    SELECT cohort_week, COUNT(*) AS cohort_users
    FROM signup_cohorts
    GROUP BY cohort_week
), weekly_activity AS (
    SELECT DISTINCT
        s.user_id,
        s.cohort_week,
        date_diff('week', s.cohort_week, date_trunc('week', o.completed_ts))
            AS weeks_since_signup
    FROM signup_cohorts AS s
    JOIN orders AS o ON o.user_id = s.user_id
    WHERE o.status = 'completed'
      AND o.completed_ts IS NOT NULL
      AND o.completed_ts >= s.cohort_week
), retained AS (
    SELECT cohort_week, weeks_since_signup, COUNT(DISTINCT user_id) AS retained_users
    FROM weekly_activity
    GROUP BY cohort_week, weeks_since_signup
)
SELECT
    r.cohort_week,
    r.weeks_since_signup,
    c.cohort_users,
    r.retained_users,
    r.retained_users::DOUBLE / NULLIF(c.cohort_users, 0) AS retention_rate
FROM retained AS r
JOIN cohort_sizes AS c USING (cohort_week)
WHERE r.weeks_since_signup >= 0;

CREATE OR REPLACE VIEW first_order_cohorts AS
WITH first_orders AS (
    SELECT
        user_id,
        order_id,
        completed_ts,
        ROW_NUMBER() OVER (
            PARTITION BY user_id
            ORDER BY completed_ts, order_id
        ) AS order_number
    FROM orders
    WHERE status = 'completed' AND completed_ts IS NOT NULL
)
SELECT
    date_trunc('week', completed_ts) AS first_order_week,
    COUNT(*) AS first_order_users
FROM first_orders
WHERE order_number = 1
GROUP BY first_order_week;
