from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.build_features import build_feature_frame, build_features, build_quality_report
from src.data.generate_marketplace import generate_marketplace, write_marketplace_data

ROOT = Path(__file__).parents[1]


def test_sql_layer_builds_one_row_per_eligible_logical_assignment() -> None:
    tables = generate_marketplace(seed=31, n_users=350, days=42)

    features = build_feature_frame(tables, sql_dir=ROOT / "sql")

    assert features["user_id"].is_unique
    assert features["is_eligible"].eq(True).all()
    assert features["decision_ts"].notna().all()
    assert (features["latest_pre_treatment_event_ts"] < features["decision_ts"]).all()
    assert features[["prior_session_count", "prior_completed_order_count"]].ge(0).all().all()


def test_point_in_time_features_exclude_event_at_decision_timestamp() -> None:
    tables = generate_marketplace(seed=32, n_users=250, days=42)
    assignment = tables["experiment_assignments"].iloc[0]
    user_id = assignment["user_id"]
    decision_ts = assignment["assignment_ts"]
    orders = tables["orders"]
    matching = orders[orders["user_id"] == user_id]
    assert not matching.empty
    index = matching.index[0]
    tables["orders"].loc[index, "status"] = "completed"
    tables["orders"].loc[index, "completed_ts"] = decision_ts

    features = build_feature_frame(tables, sql_dir=ROOT / "sql")
    row = features[features["user_id"] == user_id]
    if not row.empty:
        assert (row["latest_pre_treatment_event_ts"] < row["decision_ts"]).all()


def test_quality_report_detects_documented_raw_defects(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    write_marketplace_data(raw_dir, seed=33, n_users=300, days=42)

    report = build_quality_report(
        raw_dir,
        tmp_path / "quality.csv",
        sql_dir=ROOT / "sql",
    )

    issue_types = set(report["issue_type"])
    assert "duplicate_assignment_key" in issue_types
    assert "order_before_signup" in issue_types
    assert "negative_margin_order" in issue_types


def test_build_recreates_parquet_and_quality_report(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    write_marketplace_data(raw_dir, seed=34, n_users=180, days=42)

    feature_path = processed_dir / "eligible_users.parquet"
    quality_path = processed_dir / "data_quality_issues.csv"
    features = build_features(raw_dir, feature_path, sql_dir=ROOT / "sql")
    report = build_quality_report(raw_dir, quality_path, sql_dir=ROOT / "sql")

    assert feature_path.is_file()
    assert quality_path.is_file()
    assert not features.empty
    assert isinstance(report, pd.DataFrame)
    assert {"issue_type", "issue_count"}.issubset(report.columns)
