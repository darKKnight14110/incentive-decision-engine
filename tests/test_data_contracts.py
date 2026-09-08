from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from src.data.build_features import build_feature_frame
from src.data.generate_marketplace import TABLE_NAMES, generate_marketplace
from src.data.validate_data import (
    DataContractError,
    TABLE_CONTRACTS,
    validate_feature_table,
    validate_marketplace_tables,
    validate_processed_features,
)

ROOT = Path(__file__).parents[1]


def test_every_m2_table_has_an_executable_contract() -> None:
    assert set(TABLE_CONTRACTS) == set(TABLE_NAMES)
    tables = generate_marketplace(seed=41, n_users=120, days=28)

    report = validate_marketplace_tables(tables)

    assert not report.is_valid
    check_names = {issue.check_name for issue in report.issues}
    assert "logical_key.unique" in check_names
    assert "order_ts" not in check_names
    assert (
        any(issue.check_name == "order_before_signup" for issue in report.issues)
        is False
    )
    assert any(
        issue.check_name == "margin.negative_guardrail" for issue in report.warnings
    )


def test_contract_detects_a_new_impossible_monetary_value() -> None:
    tables = generate_marketplace(seed=42, n_users=80, days=28)
    tables["orders"] = tables["orders"].copy()
    tables["orders"].loc[tables["orders"].index[0], "gross_value_inr"] = -1.0

    report = validate_marketplace_tables(tables)

    matching = [
        issue
        for issue in report.errors
        if issue.table == "orders" and issue.check_name == "gross_value_inr.minimum"
    ]
    assert matching and matching[0].row_count == 1


def test_contract_detects_orphan_foreign_keys() -> None:
    tables = generate_marketplace(seed=43, n_users=80, days=28)
    tables["sessions"] = tables["sessions"].copy()
    tables["sessions"].loc[tables["sessions"].index[0], "user_id"] = "missing-user"

    report = validate_marketplace_tables(tables)

    assert any(
        issue.table == "sessions"
        and issue.check_name == "user_id.referential_integrity"
        and issue.row_count == 1
        for issue in report.errors
    )


def test_contract_detects_refund_above_linked_order_value() -> None:
    tables = generate_marketplace(seed=45, n_users=120, days=28)
    tables["refunds"] = tables["refunds"].copy()
    refund = tables["refunds"].iloc[0]
    order_index = tables["orders"].set_index("order_id")
    tables["refunds"].loc[refund.name, "refund_amount_inr"] = (
        order_index.loc[refund["order_id"], "gross_value_inr"] + 1
    )

    report = validate_marketplace_tables(tables)

    assert any(
        issue.table == "refunds"
        and issue.check_name == "refund_amount.not_greater_than_order"
        and issue.row_count == 1
        for issue in report.errors
    )


def test_processed_feature_contract_is_checked_at_the_build_boundary() -> None:
    tables = generate_marketplace(seed=44, n_users=150, days=42)
    features = build_feature_frame(tables, sql_dir=ROOT / "sql")
    corrupted = features.copy()
    corrupted.loc[corrupted.index[0], "latest_pre_treatment_event_ts"] = corrupted.loc[
        corrupted.index[0], "decision_ts"
    ]

    report = validate_feature_table(corrupted)

    assert any(
        issue.check_name == "point_in_time.no_post_treatment_event"
        and issue.row_count == 1
        for issue in report.errors
    )
    with pytest.raises(
        DataContractError, match="point_in_time.no_post_treatment_event"
    ):
        report.raise_if_invalid()


def test_processed_feature_contract_blocks_unexpected_post_treatment_columns() -> None:
    tables = generate_marketplace(seed=46, n_users=150, days=42)
    features = build_feature_frame(tables, sql_dir=ROOT / "sql")
    corrupted = features.assign(refund_amount_inr=0.0)

    report = validate_feature_table(corrupted)

    assert any(
        issue.check_name == "columns.unexpected" and issue.row_count == 1
        for issue in report.errors
    )


def test_persisted_feature_contract_can_validate_parquet_boundary(
    tmp_path: Path,
) -> None:
    tables = generate_marketplace(seed=47, n_users=150, days=42)
    feature_path = tmp_path / "eligible_users.parquet"
    build_feature_frame(tables, sql_dir=ROOT / "sql").to_parquet(feature_path)

    report = validate_processed_features(feature_path)

    assert report.is_valid
    assert not report.issues


def test_schema_ddl_executes_in_duckdb() -> None:
    connection = duckdb.connect()
    try:
        connection.execute((ROOT / "sql/schema.sql").read_text(encoding="utf-8"))
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main'"
            ).fetchall()
        }
    finally:
        connection.close()

    assert set(TABLE_NAMES).issubset(table_names)
