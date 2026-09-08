-- Point-in-time user features.
-- Grain: one row per logical (user_id, experiment_id) assignment. The final
-- eligible_users view is one row per eligible user at decision_ts.
-- Every event join below uses a strict event_ts < decision_ts predicate.

CREATE OR REPLACE VIEW assignment_decisions AS
SELECT
    assignment_id,
    user_id,
    experiment_id,
    assignment_ts AS decision_ts,
    treatment,
    ROW_NUMBER() OVER (
        PARTITION BY user_id, experiment_id
        ORDER BY assignment_ts, assignment_id
    ) AS assignment_row_number
FROM experiment_assignments;

CREATE OR REPLACE VIEW deduplicated_assignments AS
SELECT assignment_id, user_id, experiment_id, decision_ts, treatment
FROM assignment_decisions
WHERE assignment_row_number = 1;

CREATE OR REPLACE VIEW prior_session_window_stats AS
WITH joined AS (
    SELECT
        a.user_id,
        a.decision_ts,
        s.session_id,
        s.session_ts,
        COUNT(s.session_id) OVER (PARTITION BY a.user_id, a.decision_ts)
            AS prior_session_count,
        COUNT(s.session_id) FILTER (WHERE s.cart_ts IS NOT NULL) OVER (
            PARTITION BY a.user_id, a.decision_ts
        ) AS prior_cart_session_count,
        COUNT(s.session_id) FILTER (WHERE s.checkout_ts IS NOT NULL) OVER (
            PARTITION BY a.user_id, a.decision_ts
        ) AS prior_checkout_session_count
    FROM deduplicated_assignments AS a
    LEFT JOIN sessions AS s
      ON s.user_id = a.user_id
     AND s.session_ts < a.decision_ts
)
SELECT
    user_id,
    decision_ts,
    MAX(prior_session_count) AS prior_session_count,
    MAX(prior_cart_session_count) AS prior_cart_session_count,
    MAX(prior_checkout_session_count) AS prior_checkout_session_count,
    MAX(session_ts) AS latest_prior_session_ts
FROM joined
GROUP BY user_id, decision_ts;

CREATE OR REPLACE VIEW prior_order_window_stats AS
WITH joined AS (
    SELECT
        a.user_id,
        a.decision_ts,
        o.order_id,
        o.completed_ts,
        o.gross_value_inr,
        o.contribution_margin_inr,
        COUNT(o.order_id) OVER (PARTITION BY a.user_id, a.decision_ts)
            AS prior_completed_order_count,
        SUM(o.gross_value_inr) OVER (PARTITION BY a.user_id, a.decision_ts)
            AS prior_gross_value_inr,
        SUM(o.contribution_margin_inr) OVER (PARTITION BY a.user_id, a.decision_ts)
            AS prior_contribution_margin_inr,
        COUNT(o.order_id) FILTER (
            WHERE o.completed_ts >= a.decision_ts - INTERVAL 30 DAY
        ) OVER (PARTITION BY a.user_id, a.decision_ts) AS prior_order_count_30d,
        SUM(o.contribution_margin_inr) FILTER (
            WHERE o.completed_ts >= a.decision_ts - INTERVAL 30 DAY
        ) OVER (PARTITION BY a.user_id, a.decision_ts) AS prior_margin_30d_inr
    FROM deduplicated_assignments AS a
    LEFT JOIN orders AS o
      ON o.user_id = a.user_id
     AND o.status = 'completed'
     AND o.completed_ts IS NOT NULL
     AND o.completed_ts < a.decision_ts
)
SELECT
    user_id,
    decision_ts,
    MAX(prior_completed_order_count) AS prior_completed_order_count,
    COALESCE(MAX(prior_gross_value_inr), 0) AS prior_gross_value_inr,
    COALESCE(MAX(prior_contribution_margin_inr), 0) AS prior_contribution_margin_inr,
    COALESCE(MAX(prior_order_count_30d), 0) AS prior_order_count_30d,
    COALESCE(MAX(prior_margin_30d_inr), 0) AS prior_margin_30d_inr,
    MAX(completed_ts) AS latest_prior_completed_ts
FROM joined
GROUP BY user_id, decision_ts;

CREATE OR REPLACE VIEW prior_contact_stats AS
SELECT
    a.user_id,
    a.decision_ts,
    COUNT(e.exposure_id) FILTER (
        WHERE e.exposure_ts >= a.decision_ts - INTERVAL 14 DAY
          AND e.exposure_ts < a.decision_ts
    ) AS prior_exposure_count_14d,
    MAX(e.exposure_ts) FILTER (WHERE e.exposure_ts < a.decision_ts)
        AS latest_prior_exposure_ts
FROM deduplicated_assignments AS a
LEFT JOIN exposures AS e
  ON e.user_id = a.user_id
 AND e.exposure_ts < a.decision_ts
GROUP BY a.user_id, a.decision_ts;

CREATE OR REPLACE VIEW pre_treatment_event_audit AS
SELECT user_id, decision_ts, MAX(event_ts) AS latest_pre_treatment_event_ts
FROM (
    SELECT a.user_id, a.decision_ts, s.session_ts AS event_ts
    FROM deduplicated_assignments AS a
    JOIN sessions AS s
      ON s.user_id = a.user_id AND s.session_ts < a.decision_ts
    UNION ALL
    SELECT a.user_id, a.decision_ts, o.completed_ts AS event_ts
    FROM deduplicated_assignments AS a
    JOIN orders AS o
      ON o.user_id = a.user_id
     AND o.status = 'completed'
     AND o.completed_ts IS NOT NULL
     AND o.completed_ts < a.decision_ts
    UNION ALL
    SELECT a.user_id, a.decision_ts, e.exposure_ts AS event_ts
    FROM deduplicated_assignments AS a
    JOIN exposures AS e
      ON e.user_id = a.user_id AND e.exposure_ts < a.decision_ts
) AS events
GROUP BY user_id, decision_ts;

CREATE OR REPLACE VIEW user_feature_candidates AS
SELECT
    a.assignment_id,
    a.user_id,
    a.experiment_id,
    a.decision_ts,
    a.treatment,
    u.signup_ts,
    u.city_id,
    u.engagement_score,
    u.preferred_hour,
    u.has_contact_consent,
    u.is_suppressed,
    u.is_active_city,
    date_diff('day', u.signup_ts, a.decision_ts) AS account_age_days,
    COALESCE(s.prior_session_count, 0) AS prior_session_count,
    COALESCE(s.prior_cart_session_count, 0) AS prior_cart_session_count,
    COALESCE(s.prior_checkout_session_count, 0) AS prior_checkout_session_count,
    s.latest_prior_session_ts,
    COALESCE(o.prior_completed_order_count, 0) AS prior_completed_order_count,
    COALESCE(o.prior_gross_value_inr, 0) AS prior_gross_value_inr,
    COALESCE(o.prior_contribution_margin_inr, 0) AS prior_contribution_margin_inr,
    COALESCE(o.prior_order_count_30d, 0) AS prior_order_count_30d,
    COALESCE(o.prior_margin_30d_inr, 0) AS prior_margin_30d_inr,
    o.latest_prior_completed_ts,
    date_diff('day', o.latest_prior_completed_ts, a.decision_ts)
        AS days_since_last_completed_order,
    COALESCE(c.prior_exposure_count_14d, 0) AS prior_exposure_count_14d,
    c.latest_prior_exposure_ts,
    e.latest_pre_treatment_event_ts,
    COALESCE(o.prior_completed_order_count, 0) > 0 AS has_prior_completed_order,
    (
        COALESCE(o.prior_completed_order_count, 0) > 0
        AND date_diff('day', u.signup_ts, a.decision_ts) >= 7
        AND COALESCE(c.prior_exposure_count_14d, 0) = 0
        AND u.is_active_city
        AND u.has_contact_consent
        AND NOT u.is_suppressed
    ) AS is_eligible
FROM deduplicated_assignments AS a
JOIN users AS u ON u.user_id = a.user_id
LEFT JOIN prior_session_window_stats AS s
  ON s.user_id = a.user_id AND s.decision_ts = a.decision_ts
LEFT JOIN prior_order_window_stats AS o
  ON o.user_id = a.user_id AND o.decision_ts = a.decision_ts
LEFT JOIN prior_contact_stats AS c
  ON c.user_id = a.user_id AND c.decision_ts = a.decision_ts
LEFT JOIN pre_treatment_event_audit AS e
  ON e.user_id = a.user_id AND e.decision_ts = a.decision_ts;

CREATE OR REPLACE VIEW eligible_users AS
SELECT * FROM user_feature_candidates WHERE is_eligible;
