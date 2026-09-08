-- Product analytics views.
-- Grain: each final view declares its grain in the view name and columns.
-- All views are descriptive synthetic-marketplace metrics, not measured impact.

CREATE OR REPLACE VIEW daily_active_users AS
WITH activity AS (
    SELECT user_id, CAST(session_ts AS DATE) AS activity_date
    FROM sessions
    UNION
    SELECT user_id, CAST(completed_ts AS DATE) AS activity_date
    FROM orders
    WHERE status = 'completed' AND completed_ts IS NOT NULL
)
SELECT activity_date, COUNT(DISTINCT user_id) AS active_users
FROM activity
GROUP BY activity_date;

CREATE OR REPLACE VIEW weekly_active_users AS
WITH activity AS (
    SELECT user_id, date_trunc('week', session_ts) AS activity_week
    FROM sessions
    UNION
    SELECT user_id, date_trunc('week', completed_ts) AS activity_week
    FROM orders
    WHERE status = 'completed' AND completed_ts IS NOT NULL
)
SELECT activity_week, COUNT(DISTINCT user_id) AS active_users
FROM activity
GROUP BY activity_week;

-- One row per session. Orders are deliberately not joined directly to this
-- view because a user can have many sessions and many orders.
CREATE OR REPLACE VIEW session_funnel_metrics AS
WITH session_flags AS (
    SELECT
        session_id,
        cart_ts IS NOT NULL AS reached_cart,
        checkout_ts IS NOT NULL AS reached_checkout
    FROM sessions
), stages AS (
    SELECT 1 AS stage_order, 'session' AS stage_name, COUNT(*) AS entity_count
    FROM session_flags
    UNION ALL
    SELECT 2, 'cart', COUNT(*) FILTER (WHERE reached_cart)
    FROM session_flags
    UNION ALL
    SELECT 3, 'checkout', COUNT(*) FILTER (WHERE reached_checkout)
    FROM session_flags
)
SELECT
    stage_order,
    stage_name,
    entity_count,
    LAG(entity_count) OVER (ORDER BY stage_order) AS previous_stage_count,
    entity_count::DOUBLE / NULLIF(LAG(entity_count) OVER (ORDER BY stage_order), 0)
        AS conversion_from_previous,
    LAG(entity_count) OVER (ORDER BY stage_order) - entity_count AS drop_off_count,
    'session' AS grain
FROM stages;

-- Orders do not carry a session_id in the source contract, so this companion
-- funnel defines the completed-order stage at user grain explicitly.
CREATE OR REPLACE VIEW user_funnel_metrics AS
WITH stage_users AS (
    SELECT 1 AS stage_order, 'user_with_session' AS stage_name, COUNT(DISTINCT user_id) AS entity_count
    FROM sessions
    UNION ALL
    SELECT 2, 'user_with_cart', COUNT(DISTINCT user_id)
    FROM sessions
    WHERE cart_ts IS NOT NULL
    UNION ALL
    SELECT 3, 'user_with_checkout', COUNT(DISTINCT user_id)
    FROM sessions
    WHERE checkout_ts IS NOT NULL
    UNION ALL
    SELECT 4, 'user_with_completed_order', COUNT(DISTINCT user_id)
    FROM orders
    WHERE status = 'completed'
)
SELECT
    stage_order,
    stage_name,
    entity_count,
    LAG(entity_count) OVER (ORDER BY stage_order) AS previous_stage_count,
    entity_count::DOUBLE / NULLIF(LAG(entity_count) OVER (ORDER BY stage_order), 0)
        AS conversion_from_previous,
    LAG(entity_count) OVER (ORDER BY stage_order) - entity_count AS drop_off_count,
    'user' AS grain
FROM stage_users;

CREATE OR REPLACE VIEW funnel_metrics AS
SELECT * FROM user_funnel_metrics;

CREATE OR REPLACE VIEW first_repeat_order_metrics AS
WITH completed_orders AS (
    SELECT
        user_id,
        order_id,
        completed_ts,
        gross_value_inr,
        contribution_margin_inr,
        ROW_NUMBER() OVER (
            PARTITION BY user_id
            ORDER BY completed_ts, order_id
        ) AS order_number,
        COUNT(*) OVER (PARTITION BY user_id) AS completed_order_count
    FROM orders
    WHERE status = 'completed' AND completed_ts IS NOT NULL
)
SELECT
    user_id,
    MIN(completed_ts) AS first_order_ts,
    MIN(gross_value_inr) FILTER (WHERE order_number = 1) AS first_order_value_inr,
    MIN(contribution_margin_inr) FILTER (WHERE order_number = 1)
        AS first_order_margin_inr,
    MAX(completed_order_count) AS completed_order_count,
    GREATEST(MAX(completed_order_count) - 1, 0) AS repeat_order_count,
    MAX(completed_ts) AS latest_completed_order_ts
FROM completed_orders
GROUP BY user_id;

CREATE OR REPLACE VIEW lifecycle_segments AS
WITH completed_orders AS (
    SELECT
        user_id,
        order_id,
        completed_ts,
        LAG(completed_ts) OVER (
            PARTITION BY user_id
            ORDER BY completed_ts, order_id
        ) AS previous_completed_ts
    FROM orders
    WHERE status = 'completed' AND completed_ts IS NOT NULL
), user_history AS (
    SELECT
        u.user_id,
        u.observation_end_ts,
        COUNT(o.completed_ts) AS completed_order_count,
        MAX(o.completed_ts) AS latest_completed_order_ts,
        MAX(CASE
            WHEN o.previous_completed_ts IS NOT NULL
             AND date_diff('day', o.previous_completed_ts, o.completed_ts) >= 28
            THEN 1 ELSE 0 END) AS has_long_order_gap
    FROM users AS u
    LEFT JOIN completed_orders AS o ON o.user_id = u.user_id
    GROUP BY u.user_id, u.observation_end_ts
)
SELECT
    user_id,
    completed_order_count,
    latest_completed_order_ts,
    CASE
        WHEN completed_order_count = 0 THEN 'new'
        WHEN has_long_order_gap = 1
             AND latest_completed_order_ts >= observation_end_ts - INTERVAL 14 DAY
            THEN 'resurrected'
        WHEN latest_completed_order_ts >= observation_end_ts - INTERVAL 14 DAY THEN 'active'
        WHEN latest_completed_order_ts >= observation_end_ts - INTERVAL 30 DAY THEN 'lapsing'
        ELSE 'dormant'
    END AS lifecycle_segment
FROM user_history;
