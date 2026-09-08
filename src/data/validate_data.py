"""Executable source and feature-table data contracts for the M4 gate.

The generator intentionally emits a few raw-data defects so the quality layer
can demonstrate detection. Structural violations are errors; negative-margin
orders are warnings because they are an explicit marketplace guardrail input,
not an impossible row.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import duckdb
import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_datetime64_any_dtype,
    is_integer_dtype,
    is_numeric_dtype,
)

from src.data.generate_marketplace import TABLE_NAMES

POST_TREATMENT_SOURCES = frozenset({"redemptions", "cancellations", "refunds"})


@dataclass(frozen=True)
class ForeignKey:
    column: str
    parent_table: str
    parent_column: str
    nullable: bool = False


@dataclass(frozen=True)
class ColumnContract:
    name: str
    dtype: str
    nullable: bool = False
    minimum: float | None = None
    minimum_exclusive: bool = False
    maximum: float | None = None
    allowed: frozenset[Any] | None = None


@dataclass(frozen=True)
class TableContract:
    name: str
    columns: tuple[ColumnContract, ...]
    primary_key: tuple[str, ...]
    foreign_keys: tuple[ForeignKey, ...] = ()
    logical_unique_keys: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class ValidationIssue:
    table: str
    check_name: str
    severity: str
    row_count: int
    message: str


@dataclass
class ValidationReport:
    """Collection of named contract results with a fail-fast error boundary."""

    issues: list[ValidationIssue]

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_frame(self) -> pd.DataFrame:
        columns = ["table", "check_name", "severity", "row_count", "message"]
        return pd.DataFrame(
            [
                {
                    "table": issue.table,
                    "check_name": issue.check_name,
                    "severity": issue.severity,
                    "row_count": issue.row_count,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
            columns=columns,
        )

    def raise_if_invalid(self) -> None:
        if self.errors:
            details = "; ".join(
                f"{issue.table}.{issue.check_name}: {issue.message}"
                for issue in self.errors
            )
            raise DataContractError(details)


class DataContractError(ValueError):
    """Raised when an error-severity contract does not hold."""


def _column(
    name: str,
    dtype: str,
    *,
    nullable: bool = False,
    minimum: float | None = None,
    minimum_exclusive: bool = False,
    maximum: float | None = None,
    allowed: set[Any] | None = None,
) -> ColumnContract:
    return ColumnContract(
        name=name,
        dtype=dtype,
        nullable=nullable,
        minimum=minimum,
        minimum_exclusive=minimum_exclusive,
        maximum=maximum,
        allowed=frozenset(allowed) if allowed is not None else None,
    )


def _contract_definitions() -> dict[str, TableContract]:
    actions = {"no_offer", "small_offer", "large_offer"}
    offer_actions = {"small_offer", "large_offer"}
    return {
        "users": TableContract(
            "users",
            (
                _column("user_id", "string"),
                _column("signup_ts", "timestamp"),
                _column("city_id", "string"),
                _column("engagement_score", "numeric", minimum=0, maximum=1),
                _column("treatment_sensitivity", "numeric", minimum=0, maximum=1),
                _column("preferred_hour", "integer", minimum=0, maximum=23),
                _column("has_contact_consent", "boolean"),
                _column("is_suppressed", "boolean"),
                _column("is_active_city", "boolean"),
                _column("observation_end_ts", "timestamp"),
                _column(
                    "lifecycle_state",
                    "string",
                    allowed={"new", "active", "lapsing", "dormant", "resurrected"},
                ),
            ),
            ("user_id",),
        ),
        "merchants": TableContract(
            "merchants",
            (
                _column("merchant_id", "string"),
                _column("city_id", "string"),
                _column("category", "string"),
                _column(
                    "base_prep_minutes", "integer", minimum=1, minimum_exclusive=True
                ),
                _column("variable_cost_rate", "numeric", minimum=0, maximum=1.5),
                _column("active_from_ts", "timestamp"),
                _column("is_active", "boolean"),
            ),
            ("merchant_id",),
        ),
        "offers": TableContract(
            "offers",
            (
                _column("offer_id", "string"),
                _column("action", "string", allowed=actions),
                _column("face_value_inr", "numeric", minimum=0),
                _column("expected_redemption_rate", "numeric", minimum=0, maximum=1),
                _column("valid_from_ts", "timestamp"),
                _column("valid_to_ts", "timestamp"),
                _column("max_uses_per_customer", "integer", minimum=0),
            ),
            ("offer_id",),
        ),
        "sessions": TableContract(
            "sessions",
            (
                _column("session_id", "string"),
                _column("user_id", "string"),
                _column("session_ts", "timestamp"),
                _column("city_id", "string"),
                _column("channel", "string", allowed={"app", "web", "email"}),
                _column("device", "string", allowed={"ios", "android", "desktop"}),
                _column("cart_ts", "timestamp", nullable=True),
                _column("checkout_ts", "timestamp", nullable=True),
            ),
            ("session_id",),
            (ForeignKey("user_id", "users", "user_id"),),
        ),
        "orders": TableContract(
            "orders",
            (
                _column("order_id", "string"),
                _column("user_id", "string"),
                _column("assigned_treatment", "string", allowed=actions),
                _column("merchant_id", "string"),
                _column("city_id", "string"),
                _column("order_ts", "timestamp"),
                _column("completed_ts", "timestamp", nullable=True),
                _column("status", "string", allowed={"completed", "cancelled"}),
                _column(
                    "gross_value_inr", "numeric", minimum=0, minimum_exclusive=True
                ),
                _column("variable_cost_inr", "numeric", minimum=0),
                _column("contribution_margin_inr", "numeric"),
                _column(
                    "delivery_minutes", "integer", minimum=1, minimum_exclusive=True
                ),
            ),
            ("order_id",),
            (
                ForeignKey("user_id", "users", "user_id"),
                ForeignKey("merchant_id", "merchants", "merchant_id"),
            ),
        ),
        "experiment_assignments": TableContract(
            "experiment_assignments",
            (
                _column("assignment_id", "string"),
                _column("user_id", "string"),
                _column("experiment_id", "string"),
                _column("assignment_ts", "timestamp"),
                _column("treatment", "string", allowed=actions),
            ),
            ("assignment_id",),
            (ForeignKey("user_id", "users", "user_id"),),
            (("user_id", "experiment_id"),),
        ),
        "exposures": TableContract(
            "exposures",
            (
                _column("exposure_id", "string"),
                _column("assignment_id", "string", nullable=True),
                _column("user_id", "string"),
                _column("campaign_id", "string"),
                _column("offer_id", "string"),
                _column("action", "string", allowed=offer_actions),
                _column("exposure_ts", "timestamp"),
                _column("city_id", "string"),
                _column("channel", "string"),
            ),
            ("exposure_id",),
            (
                ForeignKey(
                    "assignment_id", "experiment_assignments", "assignment_id", True
                ),
                ForeignKey("user_id", "users", "user_id"),
                ForeignKey("offer_id", "offers", "offer_id"),
            ),
        ),
        "redemptions": TableContract(
            "redemptions",
            (
                _column("redemption_id", "string"),
                _column("exposure_id", "string"),
                _column("user_id", "string"),
                _column("order_id", "string", nullable=True),
                _column("offer_id", "string"),
                _column("redeemed_ts", "timestamp"),
                _column("discount_inr", "numeric", minimum=0),
            ),
            ("redemption_id",),
            (
                ForeignKey("exposure_id", "exposures", "exposure_id"),
                ForeignKey("user_id", "users", "user_id"),
                ForeignKey("order_id", "orders", "order_id", True),
                ForeignKey("offer_id", "offers", "offer_id"),
            ),
        ),
        "cancellations": TableContract(
            "cancellations",
            (
                _column("cancellation_id", "string"),
                _column("order_id", "string"),
                _column("user_id", "string"),
                _column("cancellation_ts", "timestamp"),
                _column("reason", "string"),
            ),
            ("cancellation_id",),
            (
                ForeignKey("order_id", "orders", "order_id"),
                ForeignKey("user_id", "users", "user_id"),
            ),
        ),
        "refunds": TableContract(
            "refunds",
            (
                _column("refund_id", "string"),
                _column("order_id", "string"),
                _column("user_id", "string"),
                _column("refund_ts", "timestamp"),
                _column(
                    "refund_amount_inr", "numeric", minimum=0, minimum_exclusive=True
                ),
                _column("reason", "string"),
            ),
            ("refund_id",),
            (
                ForeignKey("order_id", "orders", "order_id"),
                ForeignKey("user_id", "users", "user_id"),
            ),
        ),
        "city_hour_capacity": TableContract(
            "city_hour_capacity",
            (
                _column("city_id", "string"),
                _column("hour_ts", "timestamp"),
                _column(
                    "available_capacity_orders",
                    "integer",
                    minimum=1,
                    minimum_exclusive=True,
                ),
                _column("baseline_orders", "integer", minimum=0),
                _column("utilization", "numeric", minimum=0),
            ),
            ("city_id", "hour_ts"),
        ),
    }


TABLE_CONTRACTS = _contract_definitions()


def _add_issue(
    issues: list[ValidationIssue],
    table: str,
    check_name: str,
    severity: str,
    row_count: int,
    message: str,
) -> None:
    if row_count:
        issues.append(
            ValidationIssue(table, check_name, severity, int(row_count), message)
        )


def _is_aware_timestamp(series: pd.Series) -> bool:
    return (
        is_datetime64_any_dtype(series)
        and getattr(series.dtype, "tz", None) is not None
    )


def _check_column(
    table_name: str,
    frame: pd.DataFrame,
    contract: ColumnContract,
    issues: list[ValidationIssue],
) -> None:
    series = frame[contract.name]
    null_count = int(series.isna().sum())
    if not contract.nullable:
        _add_issue(
            issues,
            table_name,
            f"{contract.name}.not_null",
            "error",
            null_count,
            f"{null_count} null values found in a non-nullable column",
        )

    non_null = series.dropna()
    if non_null.empty:
        return
    if contract.dtype == "timestamp":
        dtype_ok = (
            is_datetime64_any_dtype(series)
            and getattr(series.dtype, "tz", None) is not None
        )
        if not dtype_ok:
            _add_issue(
                issues,
                table_name,
                f"{contract.name}.dtype",
                "error",
                len(non_null),
                "expected timezone-aware datetime values",
            )
    elif contract.dtype == "boolean":
        if not is_bool_dtype(series):
            _add_issue(
                issues,
                table_name,
                f"{contract.name}.dtype",
                "error",
                len(non_null),
                "expected boolean values",
            )
    elif contract.dtype == "integer":
        if not is_integer_dtype(series):
            _add_issue(
                issues,
                table_name,
                f"{contract.name}.dtype",
                "error",
                len(non_null),
                "expected integer values",
            )
    elif contract.dtype == "numeric":
        if not is_numeric_dtype(series) or is_bool_dtype(series):
            _add_issue(
                issues,
                table_name,
                f"{contract.name}.dtype",
                "error",
                len(non_null),
                "expected numeric values",
            )
    elif contract.dtype == "string":
        invalid_strings = int(
            (~non_null.map(lambda value: isinstance(value, str))).sum()
        )
        _add_issue(
            issues,
            table_name,
            f"{contract.name}.dtype",
            "error",
            invalid_strings,
            "expected string values",
        )

    if contract.minimum is not None and is_numeric_dtype(series):
        invalid = int(
            (
                non_null <= contract.minimum
                if contract.minimum_exclusive
                else non_null < contract.minimum
            ).sum()
        )
        comparison = ">" if contract.minimum_exclusive else ">="
        _add_issue(
            issues,
            table_name,
            f"{contract.name}.minimum",
            "error",
            invalid,
            f"values must be {comparison} {contract.minimum}",
        )
    if contract.maximum is not None and is_numeric_dtype(series):
        invalid = int((non_null > contract.maximum).sum())
        _add_issue(
            issues,
            table_name,
            f"{contract.name}.maximum",
            "error",
            invalid,
            f"values must be <= {contract.maximum}",
        )
    if contract.allowed is not None:
        invalid = int((~non_null.isin(contract.allowed)).sum())
        _add_issue(
            issues,
            table_name,
            f"{contract.name}.allowed_values",
            "error",
            invalid,
            f"values must be in {sorted(contract.allowed)}",
        )


def _check_key(
    table_name: str,
    frame: pd.DataFrame,
    key: tuple[str, ...],
    issues: list[ValidationIssue],
    check_prefix: str,
) -> None:
    null_count = int(frame[list(key)].isna().any(axis=1).sum())
    _add_issue(
        issues,
        table_name,
        f"{check_prefix}.not_null",
        "error",
        null_count,
        f"key {key} contains null values",
    )
    duplicate_count = int(frame.duplicated(subset=list(key), keep=False).sum())
    _add_issue(
        issues,
        table_name,
        f"{check_prefix}.unique",
        "error",
        duplicate_count,
        f"key {key} contains duplicate rows",
    )


def _check_foreign_key(
    table_name: str,
    frame: pd.DataFrame,
    foreign_key: ForeignKey,
    tables: Mapping[str, pd.DataFrame],
    issues: list[ValidationIssue],
) -> None:
    child = frame[foreign_key.column]
    if foreign_key.parent_table not in tables:
        _add_issue(
            issues,
            table_name,
            f"{foreign_key.column}.parent_table",
            "error",
            len(frame),
            f"parent table {foreign_key.parent_table!r} is missing",
        )
        return
    parent = tables[foreign_key.parent_table]
    if foreign_key.parent_column not in parent.columns:
        _add_issue(
            issues,
            table_name,
            f"{foreign_key.column}.parent_column",
            "error",
            len(frame),
            f"parent column {foreign_key.parent_table}.{foreign_key.parent_column!r} is missing",
        )
        return
    parent_values = set(parent[foreign_key.parent_column].dropna())
    missing = child.notna() & ~child.isin(parent_values)
    missing_count = int(missing.sum())
    _add_issue(
        issues,
        table_name,
        f"{foreign_key.column}.referential_integrity",
        "error",
        missing_count,
        f"values do not exist in {foreign_key.parent_table}.{foreign_key.parent_column}",
    )


def _check_business_rules(
    tables: Mapping[str, pd.DataFrame], issues: list[ValidationIssue]
) -> None:
    users = tables.get("users", pd.DataFrame())
    if (
        {"signup_ts", "observation_end_ts"}.issubset(users.columns)
        and _is_aware_timestamp(users["signup_ts"])
        and _is_aware_timestamp(users["observation_end_ts"])
    ):
        invalid = int((users["observation_end_ts"] < users["signup_ts"]).sum())
        _add_issue(
            issues,
            "users",
            "observation_window.monotonic",
            "error",
            invalid,
            "observation_end_ts must be on or after signup_ts",
        )

    sessions = tables.get("sessions", pd.DataFrame())
    if (
        not sessions.empty
        and {
            "session_ts",
            "cart_ts",
            "checkout_ts",
        }.issubset(sessions.columns)
        and _is_aware_timestamp(sessions["session_ts"])
    ):
        cart_is_timestamp = sessions["cart_ts"].isna().all() or _is_aware_timestamp(
            sessions["cart_ts"]
        )
        checkout_is_timestamp = sessions[
            "checkout_ts"
        ].isna().all() or _is_aware_timestamp(sessions["checkout_ts"])
        if cart_is_timestamp and checkout_is_timestamp:
            invalid_cart = int(
                (
                    sessions["cart_ts"].notna()
                    & (sessions["cart_ts"] < sessions["session_ts"])
                ).sum()
            )
            invalid_checkout = int(
                (
                    sessions["checkout_ts"].notna()
                    & (
                        sessions["cart_ts"].isna()
                        | (sessions["checkout_ts"] < sessions["cart_ts"])
                    )
                ).sum()
            )
            _add_issue(
                issues,
                "sessions",
                "funnel_timestamps.monotonic",
                "error",
                invalid_cart + invalid_checkout,
                "cart must follow session and checkout must follow cart",
            )

    offers = tables.get("offers", pd.DataFrame())
    if (
        not offers.empty
        and {"valid_from_ts", "valid_to_ts"}.issubset(offers.columns)
        and _is_aware_timestamp(offers["valid_from_ts"])
        and _is_aware_timestamp(offers["valid_to_ts"])
    ):
        invalid_offer_window = int(
            (offers["valid_to_ts"] < offers["valid_from_ts"]).sum()
        )
        _add_issue(
            issues,
            "offers",
            "validity_window.monotonic",
            "error",
            invalid_offer_window,
            "valid_to_ts must be on or after valid_from_ts",
        )

    orders = tables.get("orders", pd.DataFrame())
    if not orders.empty and {
        "order_ts",
        "completed_ts",
        "status",
        "gross_value_inr",
        "variable_cost_inr",
        "contribution_margin_inr",
    }.issubset(orders.columns):
        timestamps_valid = _is_aware_timestamp(orders["order_ts"]) and (
            orders["completed_ts"].isna().all()
            or _is_aware_timestamp(orders["completed_ts"])
        )
        invalid_completion = (
            int(
                (
                    orders["completed_ts"].notna()
                    & (orders["completed_ts"] < orders["order_ts"])
                ).sum()
            )
            if timestamps_valid
            else 0
        )
        status_mismatch = int(
            (
                ((orders["status"] == "completed") & orders["completed_ts"].isna())
                | ((orders["status"] == "cancelled") & orders["completed_ts"].notna())
            ).sum()
        )
        amounts_are_numeric = all(
            is_numeric_dtype(orders[column])
            for column in (
                "gross_value_inr",
                "variable_cost_inr",
                "contribution_margin_inr",
            )
        )
        margin_reconciliation = (
            int(
                (
                    (
                        orders["gross_value_inr"]
                        - orders["variable_cost_inr"]
                        - orders["contribution_margin_inr"]
                    ).abs()
                    > 0.02
                ).sum()
            )
            if amounts_are_numeric
            else 0
        )
        _add_issue(
            issues,
            "orders",
            "completion_timestamps.monotonic",
            "error",
            invalid_completion,
            "completed_ts must be on or after order_ts",
        )
        _add_issue(
            issues,
            "orders",
            "status_completion.consistent",
            "error",
            status_mismatch,
            "completed orders need completed_ts and cancelled orders must not have it",
        )
        _add_issue(
            issues,
            "orders",
            "margin.reconciles",
            "error",
            margin_reconciliation,
            "contribution_margin_inr must equal gross_value_inr - variable_cost_inr",
        )
        negative_margin = (
            int((orders["contribution_margin_inr"] < 0).sum())
            if is_numeric_dtype(orders["contribution_margin_inr"])
            else 0
        )
        _add_issue(
            issues,
            "orders",
            "margin.negative_guardrail",
            "warning",
            negative_margin,
            "negative-margin orders are retained for guardrail analysis",
        )

    refunds = tables.get("refunds", pd.DataFrame())
    if (
        not refunds.empty
        and not orders.empty
        and {
            "order_id",
            "user_id",
            "refund_amount_inr",
            "refund_ts",
        }.issubset(refunds.columns)
        and {"order_id", "user_id", "gross_value_inr", "order_ts"}.issubset(
            orders.columns
        )
    ):
        order_amounts = orders.set_index("order_id")["gross_value_inr"]
        order_users = orders.set_index("order_id")["user_id"]
        linked_amounts = refunds["order_id"].map(order_amounts)
        invalid_refunds = (
            int(
                (
                    linked_amounts.notna()
                    & (refunds["refund_amount_inr"] > linked_amounts)
                ).sum()
            )
            if is_numeric_dtype(refunds["refund_amount_inr"])
            and is_numeric_dtype(orders["gross_value_inr"])
            else 0
        )
        _add_issue(
            issues,
            "refunds",
            "refund_amount.not_greater_than_order",
            "error",
            invalid_refunds,
            "refund_amount_inr must not exceed the linked order gross value",
        )
        invalid_refund_user = int(
            (
                refunds["user_id"].map(order_users).notna()
                & (refunds["user_id"] != refunds["order_id"].map(order_users))
            ).sum()
        )
        _add_issue(
            issues,
            "refunds",
            "user_matches_order",
            "error",
            invalid_refund_user,
            "refund user_id must match the linked order user_id",
        )

    redemptions = tables.get("redemptions", pd.DataFrame())
    exposures = tables.get("exposures", pd.DataFrame())
    if (
        not redemptions.empty
        and not exposures.empty
        and {
            "exposure_id",
            "user_id",
            "offer_id",
            "redeemed_ts",
        }.issubset(redemptions.columns)
        and {"exposure_id", "user_id", "offer_id", "exposure_ts"}.issubset(
            exposures.columns
        )
    ):
        exposure_lookup = exposures.set_index("exposure_id")
        exposure_ts = redemptions["exposure_id"].map(exposure_lookup["exposure_ts"])
        exposure_users = redemptions["exposure_id"].map(exposure_lookup["user_id"])
        exposure_offers = redemptions["exposure_id"].map(exposure_lookup["offer_id"])
        invalid_redemption_time = (
            int(
                (exposure_ts.notna() & (redemptions["redeemed_ts"] < exposure_ts)).sum()
            )
            if _is_aware_timestamp(redemptions["redeemed_ts"])
            and _is_aware_timestamp(exposures["exposure_ts"])
            else 0
        )
        invalid_redemption_user = int(
            (exposure_users.notna() & (redemptions["user_id"] != exposure_users)).sum()
        )
        invalid_redemption_offer = int(
            (
                exposure_offers.notna() & (redemptions["offer_id"] != exposure_offers)
            ).sum()
        )
        _add_issue(
            issues,
            "redemptions",
            "redeemed_after_exposure",
            "error",
            invalid_redemption_time,
            "redeemed_ts must be on or after exposure_ts",
        )
        _add_issue(
            issues,
            "redemptions",
            "user_matches_exposure",
            "error",
            invalid_redemption_user,
            "redemption user_id must match the exposure user_id",
        )
        _add_issue(
            issues,
            "redemptions",
            "offer_matches_exposure",
            "error",
            invalid_redemption_offer,
            "redemption offer_id must match the exposure offer_id",
        )

    cancellations = tables.get("cancellations", pd.DataFrame())
    if (
        not cancellations.empty
        and not orders.empty
        and {"order_id", "cancellation_ts"}.issubset(cancellations.columns)
        and {"order_id", "order_ts"}.issubset(orders.columns)
    ):
        order_ts = orders.set_index("order_id")["order_ts"]
        invalid_cancellation_time = (
            int(
                (
                    cancellations["order_id"].map(order_ts).notna()
                    & (
                        cancellations["cancellation_ts"]
                        < cancellations["order_id"].map(order_ts)
                    )
                ).sum()
            )
            if _is_aware_timestamp(cancellations["cancellation_ts"])
            and _is_aware_timestamp(orders["order_ts"])
            else 0
        )
        _add_issue(
            issues,
            "cancellations",
            "cancellation_after_order",
            "error",
            invalid_cancellation_time,
            "cancellation_ts must be on or after order_ts",
        )

    if (
        not refunds.empty
        and not orders.empty
        and {"order_id", "refund_ts"}.issubset(refunds.columns)
        and {"order_id", "order_ts"}.issubset(orders.columns)
    ):
        order_ts = orders.set_index("order_id")["order_ts"]
        invalid_refund_time = (
            int(
                (
                    refunds["order_id"].map(order_ts).notna()
                    & (refunds["refund_ts"] < refunds["order_id"].map(order_ts))
                ).sum()
            )
            if _is_aware_timestamp(refunds["refund_ts"])
            and _is_aware_timestamp(orders["order_ts"])
            else 0
        )
        _add_issue(
            issues,
            "refunds",
            "refund_after_order",
            "error",
            invalid_refund_time,
            "refund_ts must be on or after order_ts",
        )

    capacity = tables.get("city_hour_capacity", pd.DataFrame())
    if (
        not capacity.empty
        and {
            "baseline_orders",
            "available_capacity_orders",
            "utilization",
        }.issubset(capacity.columns)
        and all(
            is_numeric_dtype(capacity[column])
            for column in (
                "baseline_orders",
                "available_capacity_orders",
                "utilization",
            )
        )
    ):
        expected_utilization = (
            capacity["baseline_orders"] / capacity["available_capacity_orders"]
        )
        invalid_utilization = int(
            (capacity["utilization"] - expected_utilization).abs().gt(0.01).sum()
        )
        _add_issue(
            issues,
            "city_hour_capacity",
            "utilization.reconciles",
            "error",
            invalid_utilization,
            "utilization must reconcile to baseline_orders / available_capacity_orders",
        )

    assignments = tables.get("experiment_assignments", pd.DataFrame())
    if (
        not exposures.empty
        and not assignments.empty
        and {"assignment_id", "exposure_ts"}.issubset(exposures.columns)
        and {"assignment_id", "assignment_ts"}.issubset(assignments.columns)
    ):
        assignment_ts = assignments.drop_duplicates("assignment_id").set_index(
            "assignment_id"
        )["assignment_ts"]
        exposure_assignment_ts = exposures["assignment_id"].map(assignment_ts)
        invalid_order = (
            int(
                (
                    exposure_assignment_ts.notna()
                    & (exposures["exposure_ts"] < exposure_assignment_ts)
                ).sum()
            )
            if _is_aware_timestamp(exposures["exposure_ts"])
            and _is_aware_timestamp(assignments["assignment_ts"])
            else 0
        )
        _add_issue(
            issues,
            "exposures",
            "exposure_after_assignment",
            "warning",
            invalid_order,
            "exposure_ts should be on or after assignment_ts",
        )


def validate_marketplace_tables(
    tables: Mapping[str, pd.DataFrame],
) -> ValidationReport:
    """Validate all 11 raw tables and cross-table business rules."""
    issues: list[ValidationIssue] = []
    expected_tables = set(TABLE_CONTRACTS)
    missing_tables = expected_tables - set(tables)
    extra_tables = set(tables) - expected_tables
    _add_issue(
        issues,
        "marketplace",
        "tables.missing",
        "error",
        len(missing_tables),
        f"missing tables: {sorted(missing_tables)}",
    )
    _add_issue(
        issues,
        "marketplace",
        "tables.unexpected",
        "error",
        len(extra_tables),
        f"unexpected tables: {sorted(extra_tables)}",
    )

    for table_name, contract in TABLE_CONTRACTS.items():
        if table_name not in tables:
            continue
        frame = tables[table_name]
        if not isinstance(frame, pd.DataFrame):
            _add_issue(
                issues,
                table_name,
                "table.type",
                "error",
                1,
                "table must be a pandas DataFrame",
            )
            continue
        expected_columns = {column.name for column in contract.columns}
        missing_columns = expected_columns - set(frame.columns)
        extra_columns = set(frame.columns) - expected_columns
        _add_issue(
            issues,
            table_name,
            "columns.missing",
            "error",
            len(missing_columns),
            f"missing columns: {sorted(missing_columns)}",
        )
        _add_issue(
            issues,
            table_name,
            "columns.unexpected",
            "error",
            len(extra_columns),
            f"unexpected columns: {sorted(extra_columns)}",
        )
        if missing_columns:
            continue
        for column in contract.columns:
            _check_column(table_name, frame, column, issues)
        _check_key(table_name, frame, contract.primary_key, issues, "primary_key")
        for logical_key in contract.logical_unique_keys:
            _check_key(table_name, frame, logical_key, issues, "logical_key")
        for foreign_key in contract.foreign_keys:
            _check_foreign_key(table_name, frame, foreign_key, tables, issues)

    _check_business_rules(tables, issues)
    return ValidationReport(issues)


FEATURE_COLUMNS = (
    "assignment_id",
    "user_id",
    "experiment_id",
    "decision_ts",
    "treatment",
    "signup_ts",
    "city_id",
    "engagement_score",
    "preferred_hour",
    "has_contact_consent",
    "is_suppressed",
    "is_active_city",
    "account_age_days",
    "prior_session_count",
    "prior_cart_session_count",
    "prior_checkout_session_count",
    "latest_prior_session_ts",
    "prior_completed_order_count",
    "prior_gross_value_inr",
    "prior_contribution_margin_inr",
    "prior_order_count_30d",
    "prior_margin_30d_inr",
    "latest_prior_completed_ts",
    "days_since_last_completed_order",
    "prior_exposure_count_14d",
    "latest_prior_exposure_ts",
    "latest_pre_treatment_event_ts",
    "has_prior_completed_order",
    "is_eligible",
)

FEATURE_CONTRACTS = tuple(
    [
        _column("assignment_id", "string"),
        _column("user_id", "string"),
        _column("experiment_id", "string"),
        _column("decision_ts", "timestamp"),
        _column(
            "treatment",
            "string",
            allowed={"no_offer", "small_offer", "large_offer"},
        ),
        _column("signup_ts", "timestamp"),
        _column("city_id", "string"),
        _column("engagement_score", "numeric", minimum=0, maximum=1),
        _column("preferred_hour", "integer", minimum=0, maximum=23),
        _column("has_contact_consent", "boolean"),
        _column("is_suppressed", "boolean"),
        _column("is_active_city", "boolean"),
        _column("account_age_days", "integer", minimum=0),
        _column("prior_session_count", "integer", minimum=0),
        _column("prior_cart_session_count", "integer", minimum=0),
        _column("prior_checkout_session_count", "integer", minimum=0),
        _column("latest_prior_session_ts", "timestamp", nullable=True),
        _column("prior_completed_order_count", "integer", minimum=0),
        _column("prior_gross_value_inr", "numeric", minimum=0),
        _column("prior_contribution_margin_inr", "numeric"),
        _column("prior_order_count_30d", "integer", minimum=0),
        _column("prior_margin_30d_inr", "numeric"),
        _column("latest_prior_completed_ts", "timestamp", nullable=True),
        _column("days_since_last_completed_order", "integer", minimum=0),
        _column("prior_exposure_count_14d", "integer", minimum=0),
        _column("latest_prior_exposure_ts", "timestamp", nullable=True),
        _column("latest_pre_treatment_event_ts", "timestamp", nullable=True),
        _column("has_prior_completed_order", "boolean"),
        _column("is_eligible", "boolean"),
    ]
)


def validate_feature_table(features: pd.DataFrame) -> ValidationReport:
    """Validate the processed one-row-per-eligible-user modeling table."""
    issues: list[ValidationIssue] = []
    table_name = "eligible_users"
    if not isinstance(features, pd.DataFrame):
        return ValidationReport(
            [
                ValidationIssue(
                    table_name, "table.type", "error", 1, "expected DataFrame"
                )
            ]
        )

    missing = set(FEATURE_COLUMNS) - set(features.columns)
    _add_issue(
        issues,
        table_name,
        "columns.missing",
        "error",
        len(missing),
        f"missing columns: {sorted(missing)}",
    )
    unexpected = set(features.columns) - set(FEATURE_COLUMNS)
    _add_issue(
        issues,
        table_name,
        "columns.unexpected",
        "error",
        len(unexpected),
        f"unexpected columns: {sorted(unexpected)}",
    )
    post_treatment_columns = sorted(set(features.columns) & POST_TREATMENT_SOURCES)
    _add_issue(
        issues,
        table_name,
        "post_treatment_sources.blocked",
        "error",
        len(post_treatment_columns),
        f"post-treatment source columns are not allowed: {post_treatment_columns}",
    )
    if missing:
        return ValidationReport(issues)

    _check_key(table_name, features, ("assignment_id",), issues, "assignment_key")
    logical_duplicates = int(
        features.duplicated(subset=["user_id", "experiment_id"], keep=False).sum()
    )
    _add_issue(
        issues,
        table_name,
        "logical_assignment_key.unique",
        "error",
        logical_duplicates,
        "processed table must contain one row per logical user-experiment assignment",
    )
    for contract in FEATURE_CONTRACTS:
        _check_column(table_name, features, contract, issues)

    timestamp_columns_valid = all(
        is_datetime64_any_dtype(features[column])
        and getattr(features[column].dtype, "tz", None) is not None
        for column in ("decision_ts", "signup_ts")
    )
    invalid_age = (
        int((features["decision_ts"] < features["signup_ts"]).sum())
        if timestamp_columns_valid
        else 0
    )
    _add_issue(
        issues,
        table_name,
        "decision_after_signup",
        "error",
        invalid_age,
        "decision_ts must be on or after signup_ts",
    )
    latest_event = features["latest_pre_treatment_event_ts"]
    latest_event_valid = (
        is_datetime64_any_dtype(latest_event)
        and getattr(latest_event.dtype, "tz", None) is not None
    )
    invalid_leakage = (
        int((latest_event.notna() & (latest_event >= features["decision_ts"])).sum())
        if latest_event_valid and timestamp_columns_valid
        else 0
    )
    _add_issue(
        issues,
        table_name,
        "point_in_time.no_post_treatment_event",
        "error",
        invalid_leakage,
        "latest source event must be strictly before decision_ts",
    )
    recency = features["days_since_last_completed_order"]
    negative_recency = (
        int((recency.notna() & (recency < 0)).sum()) if is_numeric_dtype(recency) else 0
    )
    _add_issue(
        issues,
        table_name,
        "recency.non_negative",
        "error",
        negative_recency,
        "days_since_last_completed_order must be non-negative",
    )
    ineligible_rows = (
        int((~features["is_eligible"]).sum())
        if is_bool_dtype(features["is_eligible"])
        else 0
    )
    _add_issue(
        issues,
        table_name,
        "eligibility.filtered",
        "error",
        ineligible_rows,
        "processed eligible_users table must contain only eligible rows",
    )
    return ValidationReport(issues)


def _read_raw_tables(raw_dir: str | Path) -> dict[str, pd.DataFrame]:
    source = Path(raw_dir)
    tables: dict[str, pd.DataFrame] = {}
    for table_name in TABLE_NAMES:
        path = source / f"{table_name}.csv"
        if not path.is_file():
            continue
        frame = pd.read_csv(path)
        for column in frame.columns:
            if column.endswith("_ts"):
                frame[column] = pd.to_datetime(frame[column], utc=True)
        tables[table_name] = frame
    return tables


def validate_raw_directory(raw_dir: str | Path = "data/raw") -> ValidationReport:
    """Validate all raw CSVs present in a generated data directory."""
    return validate_marketplace_tables(_read_raw_tables(raw_dir))


def validate_processed_features(
    feature_path: str | Path = "data/processed/eligible_users.parquet",
) -> ValidationReport:
    """Validate a persisted eligible-user Parquet artifact at its file boundary."""
    features = pd.read_parquet(feature_path)
    for column in features.columns:
        if column.endswith("_ts"):
            features[column] = pd.to_datetime(features[column], utc=True)
    return validate_feature_table(features)


def validate_data(raw_dir: str | Path = "data/raw") -> ValidationReport:
    """Compatibility entry point for validating the raw marketplace contract."""
    return validate_raw_directory(raw_dir)


def find_data_quality_issues(
    raw_dir: str | Path = "data/raw", sql_dir: str | Path = "sql"
) -> pd.DataFrame:
    """Return SQL quality diagnostics without mutating or repairing raw data."""
    from src.data.build_features import execute_sql_assets, load_marketplace_tables

    connection = duckdb.connect()
    try:
        load_marketplace_tables(connection, raw_dir)
        execute_sql_assets(connection, sql_dir)
        return connection.sql(
            "SELECT * FROM data_quality_issues ORDER BY issue_type"
        ).df()
    finally:
        connection.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("data/processed/data_contract_report.csv"),
    )
    parser.add_argument("--fail-on-errors", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse_args()
    report = validate_raw_directory(arguments.raw_dir)
    arguments.report_path.parent.mkdir(parents=True, exist_ok=True)
    report.to_frame().to_csv(arguments.report_path, index=False)
    print(
        f"contract_issues: {len(report.issues)} "
        f"({len(report.errors)} errors, {len(report.warnings)} warnings) "
        f"-> {arguments.report_path}"
    )
    if arguments.fail_on_errors:
        report.raise_if_invalid()
