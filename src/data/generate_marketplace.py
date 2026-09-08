"""Generate a deterministic, intentionally imperfect marketplace dataset.

This is synthetic data for pipeline development. It is not evidence of real
business impact. Every public generator accepts a seed so a failed validation
case can be reproduced exactly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

TABLE_NAMES = (
    "users",
    "sessions",
    "merchants",
    "orders",
    "offers",
    "exposures",
    "redemptions",
    "cancellations",
    "refunds",
    "experiment_assignments",
    "city_hour_capacity",
)

CITY_IDS = np.array(["city_1", "city_2", "city_3", "city_4"])
OFFER_ACTIONS = np.array(["small_offer", "large_offer"])
CATEGORIES = np.array(["grocery", "restaurant", "pharmacy", "convenience"])


def _timestamp(value: str | pd.Timestamp) -> pd.Timestamp:
    """Convert an input timestamp to UTC and reject ambiguous values."""
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        return parsed.tz_localize("UTC")
    return parsed.tz_convert("UTC")


def _validate_size(name: str, value: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be at least 1")


def _coerce_timestamps(frame: pd.DataFrame) -> pd.DataFrame:
    """Ensure every timestamp column is timezone-aware UTC."""
    for column in frame.columns:
        if column.endswith("_ts"):
            frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame


def _observation_end(start_ts: pd.Timestamp, days: int) -> pd.Timestamp:
    _validate_size("days", days)
    return start_ts + pd.Timedelta(days=days)


def generate_users(
    seed: int, n_users: int = 1_000, start_ts: str | pd.Timestamp = "2025-01-01", days: int = 42
) -> pd.DataFrame:
    """Generate one row per user with signup and pre-treatment attributes."""
    _validate_size("n_users", n_users)
    start = _timestamp(start_ts)
    rng = np.random.default_rng(seed)
    signup_span = max(1, int(days * 0.45 * 86_400))
    signup_ts = start + pd.to_timedelta(rng.integers(0, signup_span, n_users), unit="s")
    engagement = rng.beta(2.2, 3.0, n_users)
    treatment_sensitivity = rng.beta(2.0, 4.0, n_users)
    frame = pd.DataFrame(
        {
            "user_id": [f"u_{index:06d}" for index in range(1, n_users + 1)],
            "signup_ts": signup_ts,
            "city_id": rng.choice(CITY_IDS, n_users, p=[0.34, 0.28, 0.23, 0.15]),
            "engagement_score": engagement.round(4),
            "treatment_sensitivity": treatment_sensitivity.round(4),
            "preferred_hour": rng.integers(7, 23, n_users),
            "has_contact_consent": rng.random(n_users) >= 0.02,
            "is_suppressed": rng.random(n_users) < 0.03,
            "is_active_city": rng.random(n_users) >= 0.015,
            "observation_end_ts": signup_ts + pd.to_timedelta(days, unit="D"),
        }
    )
    frame["lifecycle_state"] = pd.cut(
        frame["engagement_score"],
        bins=[-np.inf, 0.15, 0.35, 0.65, np.inf],
        labels=["dormant", "lapsing", "active", "resurrected"],
    ).astype(str)
    return _coerce_timestamps(frame)


def generate_merchants(
    seed: int, n_merchants: int = 32, start_ts: str | pd.Timestamp = "2025-01-01"
) -> pd.DataFrame:
    """Generate one row per merchant with operational and cost attributes."""
    _validate_size("n_merchants", n_merchants)
    start = _timestamp(start_ts)
    rng = np.random.default_rng(seed)
    city_ids = np.resize(CITY_IDS, n_merchants).copy()
    rng.shuffle(city_ids)
    frame = pd.DataFrame(
        {
            "merchant_id": [f"m_{index:04d}" for index in range(1, n_merchants + 1)],
            "city_id": city_ids,
            "category": rng.choice(CATEGORIES, n_merchants),
            "base_prep_minutes": rng.integers(8, 36, n_merchants),
            "variable_cost_rate": rng.uniform(0.62, 0.88, n_merchants).round(4),
            "active_from_ts": start,
            "is_active": rng.random(n_merchants) >= 0.04,
        }
    )
    return _coerce_timestamps(frame)


def generate_offers(
    seed: int, start_ts: str | pd.Timestamp = "2025-01-01"
) -> pd.DataFrame:
    """Generate the offer catalogue used by exposure and assignment events."""
    _ = np.random.default_rng(seed)
    start = _timestamp(start_ts)
    return _coerce_timestamps(
        pd.DataFrame(
            {
                "offer_id": ["offer_none", "offer_small", "offer_large"],
                "action": ["no_offer", "small_offer", "large_offer"],
                "face_value_inr": [0.0, 50.0, 100.0],
                "expected_redemption_rate": [0.0, 0.35, 0.55],
                "valid_from_ts": [start] * 3,
                "valid_to_ts": [start + pd.Timedelta(days=365)] * 3,
                "max_uses_per_customer": [0, 1, 1],
            }
        )
    )


def generate_sessions(
    seed: int, users: pd.DataFrame, days: int = 42
) -> pd.DataFrame:
    """Generate one row per session with cart and checkout funnel events."""
    _validate_size("days", days)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for user in users.itertuples(index=False):
        session_count = int(rng.poisson(2.0 + 5.0 * user.engagement_score))
        available_seconds = max(3_600, int(days * 0.55 * 86_400))
        for session_number in range(session_count):
            session_ts = user.signup_ts + pd.Timedelta(
                seconds=int(rng.integers(0, available_seconds))
            )
            has_cart = bool(rng.random() < 0.32)
            has_checkout = has_cart and bool(rng.random() < 0.58)
            cart_ts = (
                session_ts + pd.Timedelta(minutes=int(rng.integers(1, 18)))
                if has_cart
                else pd.NaT
            )
            checkout_ts = (
                cart_ts + pd.Timedelta(minutes=int(rng.integers(1, 12)))
                if has_checkout
                else pd.NaT
            )
            rows.append(
                {
                    "session_id": f"s_{len(rows) + 1:08d}",
                    "user_id": user.user_id,
                    "session_ts": session_ts,
                    "city_id": user.city_id,
                    "channel": rng.choice(["app", "web", "email"], p=[0.68, 0.24, 0.08]),
                    "device": rng.choice(["ios", "android", "desktop"], p=[0.34, 0.48, 0.18]),
                    "cart_ts": cart_ts,
                    "checkout_ts": checkout_ts,
                }
            )
    if not rows:
        rows.append(
            {
                "session_id": "s_00000001",
                "user_id": users.iloc[0]["user_id"],
                "session_ts": users.iloc[0]["signup_ts"] + pd.Timedelta(hours=1),
                "city_id": users.iloc[0]["city_id"],
                "channel": "app",
                "device": "android",
                "cart_ts": pd.NaT,
                "checkout_ts": pd.NaT,
            }
        )
    return _coerce_timestamps(pd.DataFrame(rows))


def generate_orders(
    seed: int,
    users: pd.DataFrame,
    merchants: pd.DataFrame,
    days: int = 42,
    assignments: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Generate one row per order, including margin and quality-test defects."""
    _validate_size("days", days)
    rng = np.random.default_rng(seed)
    merchants_by_city = {
        city: group["merchant_id"].to_numpy()
        for city, group in merchants.groupby("city_id")
    }
    merchant_cost = merchants.set_index("merchant_id")["variable_cost_rate"].to_dict()
    treatment_by_user: dict[str, str] = {}
    if assignments is not None and not assignments.empty:
        treatment_by_user = (
            assignments.drop_duplicates(subset=["user_id", "experiment_id"])
            .set_index("user_id")["treatment"]
            .to_dict()
        )
    treatment_lift = {"no_offer": 0.0, "small_offer": 0.30, "large_offer": 0.55}
    rows: list[dict[str, Any]] = []
    for user in users.itertuples(index=False):
        assigned_treatment = treatment_by_user.get(user.user_id, "no_offer")
        order_intensity = (
            0.8
            + 2.2 * user.engagement_score
            + treatment_lift[assigned_treatment] * user.treatment_sensitivity
        )
        order_count = int(rng.poisson(order_intensity))
        for _ in range(order_count):
            city_merchants = merchants_by_city.get(
                user.city_id, merchants["merchant_id"].to_numpy()
            )
            merchant_id = str(rng.choice(city_merchants))
            order_ts = user.signup_ts + pd.Timedelta(
                seconds=int(rng.integers(3_600, max(3_601, int(days * 0.8 * 86_400))))
            )
            gross_value = float(np.clip(rng.lognormal(np.log(650), 0.52), 100, 3_000))
            cost_rate = float(merchant_cost[merchant_id] + rng.normal(0, 0.025))
            variable_cost = gross_value * float(np.clip(cost_rate, 0.45, 1.10))
            status = "cancelled" if rng.random() < 0.09 else "completed"
            completed_ts = (
                order_ts + pd.Timedelta(minutes=int(rng.integers(20, 90)))
                if status == "completed"
                else pd.NaT
            )
            rows.append(
                {
                    "order_id": f"o_{len(rows) + 1:08d}",
                    "user_id": user.user_id,
                    "assigned_treatment": assigned_treatment,
                    "merchant_id": merchant_id,
                    "city_id": user.city_id,
                    "order_ts": order_ts,
                    "completed_ts": completed_ts,
                    "status": status,
                    "gross_value_inr": round(gross_value, 2),
                    "variable_cost_inr": round(variable_cost, 2),
                    "contribution_margin_inr": round(gross_value - variable_cost, 2),
                    "delivery_minutes": int(rng.integers(18, 85)),
                }
            )
    if not rows:
        user = users.iloc[0]
        merchant_id = str(merchants.iloc[0]["merchant_id"])
        rows.append(
            {
                "order_id": "o_00000001",
                "user_id": user["user_id"],
                "assigned_treatment": treatment_by_user.get(user["user_id"], "no_offer"),
                "merchant_id": merchant_id,
                "city_id": user["city_id"],
                "order_ts": user["signup_ts"] + pd.Timedelta(hours=1),
                "completed_ts": user["signup_ts"] + pd.Timedelta(hours=2),
                "status": "completed",
                "gross_value_inr": 650.0,
                "variable_cost_inr": 500.0,
                "contribution_margin_inr": 150.0,
                "delivery_minutes": 35,
            }
        )
    frame = _coerce_timestamps(pd.DataFrame(rows))
    user_lookup = users.set_index("user_id")["signup_ts"]
    defect_count = max(1, int(np.ceil(len(frame) * 0.005)))
    defect_indices = rng.choice(frame.index.to_numpy(), defect_count, replace=False)
    frame.loc[defect_indices, "order_ts"] = [
        user_lookup[frame.loc[index, "user_id"]] - pd.Timedelta(hours=1)
        for index in defect_indices
    ]
    negative_count = max(1, int(np.ceil(len(frame) * 0.01)))
    negative_indices = rng.choice(frame.index.to_numpy(), negative_count, replace=False)
    frame.loc[negative_indices, "variable_cost_inr"] = (
        frame.loc[negative_indices, "gross_value_inr"] * 1.15
    ).round(2)
    frame.loc[negative_indices, "contribution_margin_inr"] = (
        frame.loc[negative_indices, "gross_value_inr"]
        - frame.loc[negative_indices, "variable_cost_inr"]
    ).round(2)
    if not (frame["status"] == "cancelled").any() and len(frame) > 1:
        frame.loc[frame.index[-1], "status"] = "cancelled"
        frame.loc[frame.index[-1], "completed_ts"] = pd.NaT
    if not (frame["status"] == "completed").any():
        frame.loc[frame.index[0], "status"] = "completed"
        frame.loc[frame.index[0], "completed_ts"] = (
            frame.loc[frame.index[0], "order_ts"] + pd.Timedelta(minutes=30)
        )
    return _coerce_timestamps(frame)


def generate_exposures(
    seed: int,
    users: pd.DataFrame,
    offers: pd.DataFrame,
    assignments: pd.DataFrame | None = None,
    days: int = 42,
) -> pd.DataFrame:
    """Generate one promotional send for each assigned non-control user."""
    _validate_size("days", days)
    rng = np.random.default_rng(seed)
    offer_by_action = offers.set_index("action")
    if assignments is None:
        assignment_rows = pd.DataFrame(
            {
                "assignment_id": [None] * len(users),
                "user_id": users["user_id"].to_numpy(),
                "treatment": rng.choice(
                    ["small_offer", "large_offer"], len(users), p=[0.65, 0.35]
                ),
            }
        )
    else:
        assignment_rows = assignments.drop_duplicates(
            subset=["user_id", "experiment_id"]
        )[["assignment_id", "user_id", "treatment"]]
    user_lookup = users.set_index("user_id")
    rows: list[dict[str, Any]] = []
    for assignment in assignment_rows.itertuples(index=False):
        if assignment.treatment == "no_offer" or assignment.user_id not in user_lookup.index:
            continue
        user = user_lookup.loc[assignment.user_id]
        offer = offer_by_action.loc[assignment.treatment]
        exposure_ts = user["signup_ts"] + pd.Timedelta(
            seconds=int(rng.integers(3_600, max(3_601, int(days * 0.85 * 86_400))))
        )
        rows.append(
            {
                "exposure_id": f"x_{len(rows) + 1:08d}",
                "assignment_id": assignment.assignment_id,
                "user_id": assignment.user_id,
                "campaign_id": "camp_m2_weekly",
                "offer_id": offer["offer_id"],
                "action": assignment.treatment,
                "exposure_ts": exposure_ts,
                "city_id": user["city_id"],
                "channel": rng.choice(["push", "email", "in_app"], p=[0.48, 0.22, 0.30]),
            }
        )
    if not rows:
        user = users.iloc[0]
        action = "small_offer"
        offer = offer_by_action.loc[action]
        rows.append(
            {
                "exposure_id": "x_00000001",
                "assignment_id": None,
                "user_id": user["user_id"],
                "campaign_id": "camp_m2_weekly",
                "offer_id": offer["offer_id"],
                "action": action,
                "exposure_ts": user["signup_ts"] + pd.Timedelta(hours=1),
                "city_id": user["city_id"],
                "channel": "push",
            }
        )
    return _coerce_timestamps(pd.DataFrame(rows))


def generate_redemptions(
    seed: int, exposures: pd.DataFrame, orders: pd.DataFrame, offers: pd.DataFrame
) -> pd.DataFrame:
    """Generate redeemed offers as post-exposure events tied to an order."""
    rng = np.random.default_rng(seed)
    offer_lookup = offers.set_index("offer_id")
    completed_by_user = {
        user_id: group.sort_values("order_ts")
        for user_id, group in orders.loc[orders["status"] == "completed"].groupby("user_id")
    }
    use_counts: dict[tuple[str, str], int] = {}
    rows: list[dict[str, Any]] = []
    for exposure in exposures.itertuples(index=False):
        redemption_rate = float(offer_lookup.loc[exposure.offer_id, "expected_redemption_rate"])
        if rng.random() >= redemption_rate:
            continue
        max_uses = int(offer_lookup.loc[exposure.offer_id, "max_uses_per_customer"])
        use_key = (exposure.user_id, exposure.offer_id)
        if use_counts.get(use_key, 0) >= max_uses:
            continue
        user_orders = completed_by_user.get(exposure.user_id)
        compatible = (
            user_orders.loc[user_orders["order_ts"] >= exposure.exposure_ts]
            if user_orders is not None
            else orders.iloc[0:0]
        )
        order = compatible.iloc[0] if not compatible.empty else None
        face_value = float(offer_lookup.loc[exposure.offer_id, "face_value_inr"])
        order_id = str(order["order_id"]) if order is not None else None
        redeemed_ts = (
            order["order_ts"]
            if order is not None
            else exposure.exposure_ts + pd.Timedelta(minutes=30)
        )
        rows.append(
            {
                "redemption_id": f"r_{len(rows) + 1:08d}",
                "exposure_id": exposure.exposure_id,
                "user_id": exposure.user_id,
                "order_id": order_id,
                "offer_id": exposure.offer_id,
                "redeemed_ts": redeemed_ts,
                "discount_inr": face_value,
            }
        )
        use_counts[use_key] = use_counts.get(use_key, 0) + 1
    if not rows:
        exposure = exposures.iloc[0]
        order_id = None
        rows.append(
            {
                "redemption_id": "r_00000001",
                "exposure_id": exposure["exposure_id"],
                "user_id": exposure["user_id"],
                "order_id": order_id,
                "offer_id": exposure["offer_id"],
                "redeemed_ts": exposure["exposure_ts"] + pd.Timedelta(minutes=30),
                "discount_inr": float(offer_lookup.loc[exposure["offer_id"], "face_value_inr"]),
            }
        )
    return _coerce_timestamps(
        pd.DataFrame(
            rows,
            columns=[
                "redemption_id",
                "exposure_id",
                "user_id",
                "order_id",
                "offer_id",
                "redeemed_ts",
                "discount_inr",
            ],
        )
    )


def generate_cancellations(seed: int, orders: pd.DataFrame) -> pd.DataFrame:
    """Generate one row per cancelled order."""
    rng = np.random.default_rng(seed)
    cancelled = orders.loc[orders["status"] == "cancelled"]
    rows = [
        {
            "cancellation_id": f"c_{index:08d}",
            "order_id": order.order_id,
            "user_id": order.user_id,
            "cancellation_ts": order.order_ts + pd.Timedelta(minutes=int(rng.integers(2, 45))),
            "reason": rng.choice(["late_delivery", "changed_mind", "merchant_unavailable"]),
        }
        for index, order in enumerate(cancelled.itertuples(index=False), start=1)
    ]
    return _coerce_timestamps(
        pd.DataFrame(
            rows,
            columns=[
                "cancellation_id",
                "order_id",
                "user_id",
                "cancellation_ts",
                "reason",
            ],
        )
    )


def generate_refunds(seed: int, orders: pd.DataFrame) -> pd.DataFrame:
    """Generate one row per refunded completed order."""
    rng = np.random.default_rng(seed)
    completed = orders.loc[orders["status"] == "completed"]
    rows = []
    for index, order in enumerate(completed.itertuples(index=False), start=1):
        if rng.random() >= 0.07:
            continue
        rows.append(
            {
                "refund_id": f"f_{index:08d}",
                "order_id": order.order_id,
                "user_id": order.user_id,
                "refund_ts": order.completed_ts + pd.Timedelta(days=int(rng.integers(1, 8))),
                "refund_amount_inr": round(
                    float(order.gross_value_inr) * rng.uniform(0.25, 1.0), 2
                ),
                "reason": rng.choice(["quality", "missing_item", "late_delivery"]),
            }
        )
    if not rows and not completed.empty:
        order = completed.iloc[0]
        rows.append(
            {
                "refund_id": "f_00000001",
                "order_id": order["order_id"],
                "user_id": order["user_id"],
                "refund_ts": order["completed_ts"] + pd.Timedelta(days=1),
                "refund_amount_inr": round(float(order["gross_value_inr"]) * 0.5, 2),
                "reason": "quality",
            }
        )
    return _coerce_timestamps(
        pd.DataFrame(
            rows,
            columns=[
                "refund_id",
                "order_id",
                "user_id",
                "refund_ts",
                "refund_amount_inr",
                "reason",
            ],
        )
    )


def generate_experiment_assignments(
    seed: int, users: pd.DataFrame, start_ts: str | pd.Timestamp = "2025-01-01", days: int = 42
) -> pd.DataFrame:
    """Generate assignments and inject a 0.3% duplicate-key defect."""
    _validate_size("days", days)
    start = _timestamp(start_ts)
    rng = np.random.default_rng(seed)
    decision_ts = start + pd.Timedelta(days=max(1, int(days * 0.55)))
    treatments = rng.choice(
        ["no_offer", "small_offer", "large_offer"], len(users), p=[0.50, 0.30, 0.20]
    )
    if (treatments != "no_offer").sum() == 0:
        treatments[0] = "small_offer"
    frame = pd.DataFrame(
        {
            "assignment_id": [f"a_{index:08d}" for index in range(1, len(users) + 1)],
            "user_id": users["user_id"].to_numpy(),
            "experiment_id": "exp_m2_offer_v1",
            "assignment_ts": decision_ts,
            "treatment": treatments,
        }
    )
    duplicate_count = max(1, int(np.ceil(len(frame) * 0.003)))
    duplicates = frame.sample(n=duplicate_count, random_state=seed).copy()
    return _coerce_timestamps(pd.concat([frame, duplicates], ignore_index=True))


def generate_city_hour_capacity(
    seed: int, start_ts: str | pd.Timestamp = "2025-01-01", days: int = 42
) -> pd.DataFrame:
    """Generate one row per city-hour capacity snapshot."""
    _validate_size("days", days)
    start = _timestamp(start_ts)
    hours = pd.date_range(start, periods=days * 24, freq="h", inclusive="left")
    rng = np.random.default_rng(seed)
    rows = []
    for city in CITY_IDS:
        for hour_ts in hours:
            capacity = int(rng.integers(35, 110))
            seasonal_multiplier = (
                1.35
                if hour_ts.hour in {18, 19, 20, 21}
                else 0.72
                if hour_ts.hour in {2, 3, 4, 5}
                else 1.0
            )
            baseline = int(
                np.clip(
                    rng.uniform(0.45, 0.85) * capacity * seasonal_multiplier,
                    0,
                    capacity * 1.5,
                )
            )
            rows.append(
            {
                "city_id": city,
                "hour_ts": hour_ts,
                "available_capacity_orders": capacity,
                "baseline_orders": baseline,
                "utilization": round(baseline / capacity, 4),
                }
            )
    return _coerce_timestamps(pd.DataFrame(rows))


def generate_marketplace(
    seed: int = 2025,
    n_users: int = 1_000,
    start_ts: str | pd.Timestamp = "2025-01-01",
    days: int = 42,
) -> dict[str, pd.DataFrame]:
    """Generate all M2 tables from one reproducible seed."""
    users = generate_users(seed + 1, n_users, start_ts, days)
    merchants = generate_merchants(seed + 2, max(8, n_users // 30), start_ts)
    offers = generate_offers(seed + 3, start_ts)
    assignments = generate_experiment_assignments(seed + 10, users, start_ts, days)
    sessions = generate_sessions(seed + 4, users, days)
    orders = generate_orders(seed + 5, users, merchants, days, assignments)
    exposures = generate_exposures(seed + 6, users, offers, assignments, days)
    redemptions = generate_redemptions(seed + 7, exposures, orders, offers)
    cancellations = generate_cancellations(seed + 8, orders)
    refunds = generate_refunds(seed + 9, orders)
    capacity = generate_city_hour_capacity(seed + 11, start_ts, days)
    return {
        "users": users,
        "sessions": sessions,
        "merchants": merchants,
        "orders": orders,
        "offers": offers,
        "exposures": exposures,
        "redemptions": redemptions,
        "cancellations": cancellations,
        "refunds": refunds,
        "experiment_assignments": assignments,
        "city_hour_capacity": capacity,
    }


def write_marketplace_data(
    output_dir: str | Path,
    seed: int = 2025,
    n_users: int = 1_000,
    start_ts: str | pd.Timestamp = "2025-01-01",
    days: int = 42,
) -> dict[str, Path]:
    """Write generated tables as CSV files and emit a reproducibility manifest."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    tables = generate_marketplace(seed, n_users, start_ts, days)
    paths: dict[str, Path] = {}
    manifest: dict[str, Any] = {
        "seed": seed,
        "n_users": n_users,
        "start_ts": str(_timestamp(start_ts)),
        "days": days,
        "tables": {},
    }
    for table_name, table in tables.items():
        path = target / f"{table_name}.csv"
        table.to_csv(path, index=False)
        paths[table_name] = path
        manifest["tables"][table_name] = {"path": path.name, "rows": len(table)}
    with (target / "manifest.json").open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)
    return paths


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/raw", type=Path)
    parser.add_argument("--seed", default=2025, type=int)
    parser.add_argument("--n-users", default=1_000, type=int)
    parser.add_argument("--start-ts", default="2025-01-01")
    parser.add_argument("--days", default=42, type=int)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse_args()
    output = write_marketplace_data(
        arguments.output_dir,
        seed=arguments.seed,
        n_users=arguments.n_users,
        start_ts=arguments.start_ts,
        days=arguments.days,
    )
    for table_name, path in output.items():
        print(f"{table_name}: {path}")
