from __future__ import annotations

import pandas as pd
import pytest


def _timestamp(day: int, hour: int = 0, minute: int = 0) -> pd.Timestamp:
    return pd.Timestamp(year=2025, month=1, day=day, hour=hour, minute=minute, tz="UTC")


def _empty_frame(columns: list[str], numeric: set[str] | None = None) -> pd.DataFrame:
    numeric = numeric or set()
    dtype_by_column = {
        column: (
            "datetime64[ns, UTC]"
            if column.endswith("_ts")
            else "float64" if column in numeric else "object"
        )
        for column in columns
    }
    return pd.DataFrame(
        {column: pd.Series(dtype=dtype) for column, dtype in dtype_by_column.items()}
    )


@pytest.fixture
def twelve_row_marketplace() -> dict[str, pd.DataFrame]:
    """Small hand-built fixture with exact funnel, cohort, and PIT expectations."""
    user_ids = [f"u_{index:02d}" for index in range(1, 13)]
    users = pd.DataFrame(
        {
            "user_id": user_ids,
            "signup_ts": [_timestamp(1)] * 12,
            "city_id": ["city_1"] * 12,
            "engagement_score": [0.20 + index * 0.01 for index in range(12)],
            "treatment_sensitivity": [0.10] * 12,
            "preferred_hour": [12] * 12,
            "has_contact_consent": [True] * 12,
            "is_suppressed": [False] * 12,
            "is_active_city": [True] * 12,
            "observation_end_ts": [_timestamp(28)] * 12,
            "lifecycle_state": ["active"] * 12,
        }
    )
    offers = pd.DataFrame(
        {
            "offer_id": ["offer_none", "offer_small", "offer_large"],
            "action": ["no_offer", "small_offer", "large_offer"],
            "face_value_inr": [0.0, 50.0, 100.0],
            "expected_redemption_rate": [0.0, 0.35, 0.55],
            "valid_from_ts": [_timestamp(1)] * 3,
            "valid_to_ts": [pd.Timestamp("2026-01-01", tz="UTC")] * 3,
            "max_uses_per_customer": [0, 1, 1],
        }
    )
    assignments = pd.DataFrame(
        {
            "assignment_id": [f"a_{index:02d}" for index in range(1, 13)],
            "user_id": user_ids,
            "experiment_id": ["fixture_exp"] * 12,
            "assignment_ts": [_timestamp(22)] * 12,
            "treatment": ["small_offer", "no_offer"] * 6,
        }
    )
    sessions = pd.DataFrame(
        {
            "session_id": ["s_01", "s_02", "s_03", "s_04"],
            "user_id": ["u_01", "u_02", "u_03", "u_04"],
            "session_ts": [_timestamp(5), _timestamp(6), _timestamp(7), _timestamp(8)],
            "city_id": ["city_1"] * 4,
            "channel": ["app", "web", "app", "email"],
            "device": ["ios", "android", "desktop", "ios"],
            "cart_ts": [
                _timestamp(5, 0, 5),
                _timestamp(6, 0, 5),
                pd.NaT,
                _timestamp(8, 0, 5),
            ],
            "checkout_ts": [_timestamp(5, 0, 10), pd.NaT, pd.NaT, _timestamp(8, 0, 10)],
        }
    )
    orders = pd.DataFrame(
        {
            "order_id": ["o_01", "o_02", "o_03", "o_04", "o_05"],
            "user_id": ["u_01", "u_02", "u_03", "u_05", "u_05"],
            "assigned_treatment": [
                "small_offer",
                "no_offer",
                "small_offer",
                "small_offer",
                "small_offer",
            ],
            "merchant_id": ["m_01"] * 5,
            "city_id": ["city_1"] * 5,
            "order_ts": [
                _timestamp(4),
                _timestamp(22),
                _timestamp(6),
                _timestamp(7),
                _timestamp(25),
            ],
            "completed_ts": [
                _timestamp(4, 0, 30),
                _timestamp(22),
                _timestamp(6, 0, 30),
                _timestamp(7, 0, 30),
                _timestamp(25, 0, 30),
            ],
            "status": ["completed"] * 5,
            "gross_value_inr": [500.0, 600.0, 700.0, 800.0, 900.0],
            "variable_cost_inr": [400.0, 480.0, 560.0, 640.0, 720.0],
            "contribution_margin_inr": [100.0, 120.0, 140.0, 160.0, 180.0],
            "delivery_minutes": [30] * 5,
        }
    )
    capacity = pd.DataFrame(
        {
            "city_id": ["city_1"],
            "hour_ts": [_timestamp(22)],
            "available_capacity_orders": [100],
            "baseline_orders": [50],
            "utilization": [0.5],
        }
    )
    return {
        "users": users,
        "sessions": sessions,
        "merchants": pd.DataFrame(
            {
                "merchant_id": ["m_01"],
                "city_id": ["city_1"],
                "category": ["restaurant"],
                "base_prep_minutes": [20],
                "variable_cost_rate": [0.8],
                "active_from_ts": [_timestamp(1)],
                "is_active": [True],
            }
        ),
        "orders": orders,
        "offers": offers,
        "exposures": _empty_frame(
            [
                "exposure_id",
                "assignment_id",
                "user_id",
                "campaign_id",
                "offer_id",
                "action",
                "exposure_ts",
                "city_id",
                "channel",
            ]
        ),
        "redemptions": _empty_frame(
            [
                "redemption_id",
                "exposure_id",
                "user_id",
                "order_id",
                "offer_id",
                "redeemed_ts",
                "discount_inr",
            ],
            numeric={"discount_inr"},
        ),
        "cancellations": _empty_frame(
            ["cancellation_id", "order_id", "user_id", "cancellation_ts", "reason"]
        ),
        "refunds": _empty_frame(
            [
                "refund_id",
                "order_id",
                "user_id",
                "refund_ts",
                "refund_amount_inr",
                "reason",
            ],
            numeric={"refund_amount_inr"},
        ),
        "experiment_assignments": assignments,
        "city_hour_capacity": capacity,
    }
