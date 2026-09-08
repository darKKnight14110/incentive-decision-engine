-- Assignment-based experiment metrics.
-- Grain: one row per deduplicated user assignment in experiment_user_outcomes;
-- one row per treatment arm in experiment_arm_summary.
-- Assignment is the denominator. Exposure and redemption remain descriptive
-- post-assignment measures and never replace the intent-to-treat denominator.

CREATE OR REPLACE VIEW experiment_user_outcomes AS
WITH assignments AS (
    SELECT
        assignment_id,
        user_id,
        experiment_id,
        assignment_ts,
        treatment,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, experiment_id
            ORDER BY assignment_ts, assignment_id
        ) AS assignment_row_number
    FROM experiment_assignments
), deduped AS (
    SELECT * FROM assignments WHERE assignment_row_number = 1
), exposure_metrics AS (
    SELECT
        a.user_id,
        a.experiment_id,
        COUNT(DISTINCT e.exposure_id) AS exposure_count,
        COUNT(DISTINCT r.redemption_id) AS redemption_count,
        SUM(r.discount_inr) AS discount_inr
    FROM deduped AS a
    LEFT JOIN exposures AS e
      ON e.user_id = a.user_id
     AND e.exposure_ts >= a.assignment_ts
     AND e.exposure_ts < a.assignment_ts + INTERVAL 14 DAY
    LEFT JOIN redemptions AS r
      ON r.exposure_id = e.exposure_id
     AND r.redeemed_ts >= a.assignment_ts
     AND r.redeemed_ts < a.assignment_ts + INTERVAL 14 DAY
    GROUP BY a.user_id, a.experiment_id
), order_metrics AS (
    SELECT
        a.user_id,
        a.experiment_id,
        COUNT(DISTINCT o.order_id) FILTER (WHERE o.status = 'completed')
            AS completed_order_count,
        COUNT(DISTINCT o.user_id) FILTER (WHERE o.status = 'completed')
            AS completed_order_user,
        SUM(o.gross_value_inr) FILTER (WHERE o.status = 'completed')
            AS completed_gross_value_inr,
        SUM(o.contribution_margin_inr) FILTER (WHERE o.status = 'completed')
            AS completed_contribution_margin_inr,
        COUNT(DISTINCT o.order_id) FILTER (WHERE o.status = 'cancelled')
            AS cancelled_order_count
    FROM deduped AS a
    LEFT JOIN orders AS o
      ON o.user_id = a.user_id
     AND o.order_ts >= a.assignment_ts
     AND o.order_ts < a.assignment_ts + INTERVAL 14 DAY
    GROUP BY a.user_id, a.experiment_id
), cancellation_metrics AS (
    SELECT
        a.user_id,
        a.experiment_id,
        COUNT(DISTINCT c.cancellation_id) AS cancellation_event_count
    FROM deduped AS a
    LEFT JOIN cancellations AS c
      ON c.user_id = a.user_id
     AND c.cancellation_ts >= a.assignment_ts
     AND c.cancellation_ts < a.assignment_ts + INTERVAL 14 DAY
    GROUP BY a.user_id, a.experiment_id
), refund_metrics AS (
    SELECT
        a.user_id,
        a.experiment_id,
        COUNT(DISTINCT f.refund_id) AS refund_event_count,
        SUM(f.refund_amount_inr) AS refund_amount_inr
    FROM deduped AS a
    LEFT JOIN refunds AS f
      ON f.user_id = a.user_id
     AND f.refund_ts >= a.assignment_ts
     AND f.refund_ts < a.assignment_ts + INTERVAL 14 DAY
    GROUP BY a.user_id, a.experiment_id
)
SELECT
    a.assignment_id,
    a.user_id,
    a.experiment_id,
    a.assignment_ts AS decision_ts,
    a.treatment,
    COALESCE(e.exposure_count, 0) AS exposure_count,
    COALESCE(e.redemption_count, 0) AS redemption_count,
    COALESCE(e.discount_inr, 0) AS discount_inr,
    COALESCE(o.completed_order_count, 0) AS completed_order_count,
    COALESCE(o.completed_order_user, 0) AS completed_order_user,
    COALESCE(o.completed_gross_value_inr, 0) AS completed_gross_value_inr,
    COALESCE(o.completed_contribution_margin_inr, 0)
        AS completed_contribution_margin_inr,
    COALESCE(o.cancelled_order_count, 0) AS cancelled_order_count,
    COALESCE(c.cancellation_event_count, 0) AS cancellation_event_count,
    COALESCE(f.refund_event_count, 0) AS refund_event_count,
    COALESCE(f.refund_amount_inr, 0) AS refund_amount_inr
FROM deduped AS a
LEFT JOIN exposure_metrics AS e USING (user_id, experiment_id)
LEFT JOIN order_metrics AS o USING (user_id, experiment_id)
LEFT JOIN cancellation_metrics AS c USING (user_id, experiment_id)
LEFT JOIN refund_metrics AS f USING (user_id, experiment_id);

CREATE OR REPLACE VIEW experiment_arm_summary AS
SELECT
    experiment_id,
    treatment,
    COUNT(*) AS assigned_users,
    COUNT(*) FILTER (WHERE exposure_count > 0) AS exposed_users,
    COUNT(*) FILTER (WHERE redemption_count > 0) AS redeemed_users,
    COUNT(*) FILTER (WHERE completed_order_user > 0) AS completed_order_users,
    SUM(completed_order_count) AS completed_orders,
    SUM(completed_contribution_margin_inr) AS completed_contribution_margin_inr,
    SUM(discount_inr) AS discount_inr,
    SUM(cancelled_order_count) AS cancelled_orders,
    SUM(refund_amount_inr) AS refund_amount_inr,
    AVG(completed_order_user) AS completed_order_rate,
    AVG(CASE WHEN cancelled_order_count > 0 THEN 1 ELSE 0 END)::DOUBLE
        AS cancellation_user_rate,
    AVG(CASE WHEN redemption_count > 0 THEN 1 ELSE 0 END)::DOUBLE
        AS redemption_user_rate
FROM experiment_user_outcomes
GROUP BY experiment_id, treatment;
