-- M2 logical schema. Each table declares its grain and primary key.
-- Raw synthetic data intentionally contains a few contract violations; M4
-- validation should detect them before a constrained load is attempted.

CREATE TABLE users (
    user_id VARCHAR PRIMARY KEY,
    signup_ts TIMESTAMPTZ NOT NULL,
    city_id VARCHAR NOT NULL,
    engagement_score DOUBLE NOT NULL CHECK (engagement_score BETWEEN 0 AND 1),
    treatment_sensitivity DOUBLE NOT NULL CHECK (treatment_sensitivity BETWEEN 0 AND 1),
    preferred_hour INTEGER NOT NULL CHECK (preferred_hour BETWEEN 0 AND 23),
    has_contact_consent BOOLEAN NOT NULL,
    is_suppressed BOOLEAN NOT NULL,
    is_active_city BOOLEAN NOT NULL,
    observation_end_ts TIMESTAMPTZ NOT NULL,
    lifecycle_state VARCHAR NOT NULL
);

CREATE TABLE merchants (
    merchant_id VARCHAR PRIMARY KEY,
    city_id VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    base_prep_minutes INTEGER NOT NULL CHECK (base_prep_minutes > 0),
    variable_cost_rate DOUBLE NOT NULL CHECK (variable_cost_rate BETWEEN 0 AND 1.5),
    active_from_ts TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN NOT NULL
);

CREATE TABLE offers (
    offer_id VARCHAR PRIMARY KEY,
    action VARCHAR NOT NULL CHECK (action IN ('no_offer', 'small_offer', 'large_offer')),
    face_value_inr DOUBLE NOT NULL CHECK (face_value_inr >= 0),
    expected_redemption_rate DOUBLE NOT NULL CHECK (expected_redemption_rate BETWEEN 0 AND 1),
    valid_from_ts TIMESTAMPTZ NOT NULL,
    valid_to_ts TIMESTAMPTZ NOT NULL,
    max_uses_per_customer INTEGER NOT NULL CHECK (max_uses_per_customer >= 0)
);

CREATE TABLE sessions (
    session_id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL REFERENCES users(user_id),
    session_ts TIMESTAMPTZ NOT NULL,
    city_id VARCHAR NOT NULL,
    channel VARCHAR NOT NULL,
    device VARCHAR NOT NULL,
    cart_ts TIMESTAMPTZ,
    checkout_ts TIMESTAMPTZ
);

CREATE TABLE orders (
    order_id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL REFERENCES users(user_id),
    assigned_treatment VARCHAR NOT NULL CHECK (assigned_treatment IN ('no_offer', 'small_offer', 'large_offer')),
    merchant_id VARCHAR NOT NULL REFERENCES merchants(merchant_id),
    city_id VARCHAR NOT NULL,
    order_ts TIMESTAMPTZ NOT NULL,
    completed_ts TIMESTAMPTZ,
    status VARCHAR NOT NULL CHECK (status IN ('completed', 'cancelled')),
    gross_value_inr DOUBLE NOT NULL CHECK (gross_value_inr > 0),
    variable_cost_inr DOUBLE NOT NULL CHECK (variable_cost_inr >= 0),
    contribution_margin_inr DOUBLE NOT NULL,
    delivery_minutes INTEGER NOT NULL CHECK (delivery_minutes > 0)
);

CREATE TABLE experiment_assignments (
    assignment_id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL REFERENCES users(user_id),
    experiment_id VARCHAR NOT NULL,
    assignment_ts TIMESTAMPTZ NOT NULL,
    treatment VARCHAR NOT NULL CHECK (treatment IN ('no_offer', 'small_offer', 'large_offer')),
    UNIQUE (user_id, experiment_id)
);

CREATE TABLE exposures (
    exposure_id VARCHAR PRIMARY KEY,
    assignment_id VARCHAR,
    user_id VARCHAR NOT NULL REFERENCES users(user_id),
    campaign_id VARCHAR NOT NULL,
    offer_id VARCHAR NOT NULL REFERENCES offers(offer_id),
    action VARCHAR NOT NULL CHECK (action IN ('small_offer', 'large_offer')),
    exposure_ts TIMESTAMPTZ NOT NULL,
    city_id VARCHAR NOT NULL,
    channel VARCHAR NOT NULL,
    FOREIGN KEY (assignment_id) REFERENCES experiment_assignments(assignment_id)
);

CREATE TABLE redemptions (
    redemption_id VARCHAR PRIMARY KEY,
    exposure_id VARCHAR NOT NULL REFERENCES exposures(exposure_id),
    user_id VARCHAR NOT NULL REFERENCES users(user_id),
    order_id VARCHAR REFERENCES orders(order_id),
    offer_id VARCHAR NOT NULL REFERENCES offers(offer_id),
    redeemed_ts TIMESTAMPTZ NOT NULL,
    discount_inr DOUBLE NOT NULL CHECK (discount_inr >= 0)
);

CREATE TABLE cancellations (
    cancellation_id VARCHAR PRIMARY KEY,
    order_id VARCHAR NOT NULL REFERENCES orders(order_id),
    user_id VARCHAR NOT NULL REFERENCES users(user_id),
    cancellation_ts TIMESTAMPTZ NOT NULL,
    reason VARCHAR NOT NULL
);

CREATE TABLE refunds (
    refund_id VARCHAR PRIMARY KEY,
    order_id VARCHAR NOT NULL REFERENCES orders(order_id),
    user_id VARCHAR NOT NULL REFERENCES users(user_id),
    refund_ts TIMESTAMPTZ NOT NULL,
    refund_amount_inr DOUBLE NOT NULL CHECK (refund_amount_inr > 0),
    reason VARCHAR NOT NULL
);

CREATE TABLE city_hour_capacity (
    city_id VARCHAR NOT NULL,
    hour_ts TIMESTAMPTZ NOT NULL,
    available_capacity_orders INTEGER NOT NULL CHECK (available_capacity_orders > 0),
    baseline_orders INTEGER NOT NULL CHECK (baseline_orders >= 0),
    utilization DOUBLE NOT NULL CHECK (utilization >= 0),
    PRIMARY KEY (city_id, hour_ts)
);
