-- Raw-data quality diagnostics. These views report defects; they do not repair
-- the intentionally imperfect M2 source tables.

CREATE OR REPLACE VIEW data_quality_issues AS
WITH issues AS (
    SELECT 'duplicate_assignment_key' AS issue_type, COUNT(*) AS issue_count
    FROM (
        SELECT user_id, experiment_id
        FROM experiment_assignments
        GROUP BY user_id, experiment_id
        HAVING COUNT(*) > 1
    ) AS duplicate_keys
    UNION ALL
    SELECT 'order_before_signup', COUNT(*)
    FROM orders AS o
    JOIN users AS u USING (user_id)
    WHERE o.order_ts < u.signup_ts
    UNION ALL
    SELECT 'orphan_session_user', COUNT(*)
    FROM sessions AS s
    LEFT JOIN users AS u USING (user_id)
    WHERE u.user_id IS NULL
    UNION ALL
    SELECT 'orphan_order_user', COUNT(*)
    FROM orders AS o
    LEFT JOIN users AS u USING (user_id)
    WHERE u.user_id IS NULL
    UNION ALL
    SELECT 'orphan_order_merchant', COUNT(*)
    FROM orders AS o
    LEFT JOIN merchants AS m USING (merchant_id)
    WHERE m.merchant_id IS NULL
    UNION ALL
    SELECT 'orphan_exposure_user', COUNT(*)
    FROM exposures AS e
    LEFT JOIN users AS u USING (user_id)
    WHERE u.user_id IS NULL
    UNION ALL
    SELECT 'orphan_redemption_exposure', COUNT(*)
    FROM redemptions AS r
    LEFT JOIN exposures AS e USING (exposure_id)
    WHERE e.exposure_id IS NULL
    UNION ALL
    SELECT 'orphan_cancellation_order', COUNT(*)
    FROM cancellations AS c
    LEFT JOIN orders AS o USING (order_id)
    WHERE o.order_id IS NULL
    UNION ALL
    SELECT 'orphan_refund_order', COUNT(*)
    FROM refunds AS f
    LEFT JOIN orders AS o USING (order_id)
    WHERE o.order_id IS NULL
    UNION ALL
    SELECT 'negative_gross_value', COUNT(*)
    FROM orders
    WHERE gross_value_inr <= 0
    UNION ALL
    SELECT 'negative_variable_cost', COUNT(*)
    FROM orders
    WHERE variable_cost_inr < 0
    UNION ALL
    SELECT 'negative_margin_order', COUNT(*)
    FROM orders
    WHERE contribution_margin_inr < 0
    UNION ALL
    SELECT 'completed_order_missing_completion_ts', COUNT(*)
    FROM orders
    WHERE status = 'completed' AND completed_ts IS NULL
    UNION ALL
    SELECT 'cancelled_order_has_completion_ts', COUNT(*)
    FROM orders
    WHERE status = 'cancelled' AND completed_ts IS NOT NULL
    UNION ALL
    SELECT 'post_treatment_feature_leakage', COUNT(*)
    FROM user_feature_candidates
    WHERE latest_pre_treatment_event_ts >= decision_ts
    UNION ALL
    SELECT 'feature_join_multiplication', COUNT(*)
    FROM (
        SELECT user_id, decision_ts
        FROM user_feature_candidates
        GROUP BY user_id, decision_ts
        HAVING COUNT(*) > 1
    ) AS duplicate_feature_keys
)
SELECT issue_type, issue_count
FROM issues
WHERE issue_count > 0;
