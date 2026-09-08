from __future__ import annotations

from math import ceil
from pathlib import Path

import pandas as pd

from src.data.generate_marketplace import (
    TABLE_NAMES,
    generate_marketplace,
    write_marketplace_data,
)

ROOT = Path(__file__).parents[1]


def test_generation_is_reproducible_for_a_seed() -> None:
    first = generate_marketplace(seed=17, n_users=120, days=14)
    second = generate_marketplace(seed=17, n_users=120, days=14)

    assert list(first) == list(TABLE_NAMES)
    for table_name in TABLE_NAMES:
        pd.testing.assert_frame_equal(first[table_name], second[table_name])


def test_generation_has_the_m2_table_contract() -> None:
    tables = generate_marketplace(seed=3, n_users=100, days=14)

    assert set(tables) == set(TABLE_NAMES)
    assert all(isinstance(table, pd.DataFrame) for table in tables.values())
    assert all(not table.empty for table in tables.values())
    assert {"user_id", "signup_ts", "city_id"}.issubset(tables["users"].columns)
    assert {"order_id", "user_id", "order_ts", "contribution_margin_inr"}.issubset(
        tables["orders"].columns
    )


def test_generator_injects_documented_quality_warts() -> None:
    tables = generate_marketplace(seed=8, n_users=1_000, days=21)
    users = tables["users"][["user_id", "signup_ts"]]
    orders = tables["orders"].merge(users, on="user_id", how="left")

    assert (orders["order_ts"] < orders["signup_ts"]).sum() >= ceil(len(orders) * 0.005)
    assert (tables["orders"]["contribution_margin_inr"] < 0).any()

    assignments = tables["experiment_assignments"]
    duplicate_rows = assignments.duplicated(
        subset=["user_id", "experiment_id", "assignment_ts", "treatment"]
    ).sum()
    assert duplicate_rows >= ceil(1_000 * 0.003)


def test_exposures_follow_experiment_assignments() -> None:
    tables = generate_marketplace(seed=21, n_users=300, days=21)
    assignments = tables["experiment_assignments"].drop_duplicates(
        subset=["user_id", "experiment_id"]
    )
    merged = tables["exposures"].merge(
        assignments[["user_id", "treatment"]], on="user_id", how="left"
    )

    assert not merged.empty
    assert (merged["treatment"] != "no_offer").all()
    assert (merged["action"] == merged["treatment"]).all()


def test_redemptions_preserve_user_order_and_timing_contracts() -> None:
    tables = generate_marketplace(seed=22, n_users=500, days=28)
    redemptions = tables["redemptions"].merge(
        tables["exposures"][["exposure_id", "exposure_ts"]], on="exposure_id"
    )
    linked = redemptions.dropna(subset=["order_id"]).merge(
        tables["orders"][["order_id", "user_id", "order_ts", "completed_ts"]],
        on="order_id",
        suffixes=("_redemption", "_order"),
    )

    assert (linked["user_id_redemption"] == linked["user_id_order"]).all()
    assert (linked["redeemed_ts"] >= linked["exposure_ts"]).all()
    assert (linked["redeemed_ts"] >= linked["order_ts"]).all()
    assert (linked["redeemed_ts"] <= linked["completed_ts"]).all()

    max_uses = tables["offers"].set_index("offer_id")["max_uses_per_customer"]
    use_counts = tables["redemptions"].groupby(["user_id", "offer_id"]).size()
    for (_, offer_id), count in use_counts.items():
        assert count <= max_uses[offer_id]


def test_events_stay_inside_each_users_observation_window() -> None:
    tables = generate_marketplace(seed=23, n_users=250, days=14)
    users = tables["users"][["user_id", "observation_end_ts"]]
    for table_name, timestamp_column in (
        ("sessions", "session_ts"),
        ("orders", "order_ts"),
        ("exposures", "exposure_ts"),
    ):
        events = tables[table_name].merge(users, on="user_id", how="left")
        assert (events[timestamp_column] <= events["observation_end_ts"]).all()


def test_dgp_contains_heterogeneous_response_and_hour_seasonality() -> None:
    tables = generate_marketplace(seed=24, n_users=500, days=28)
    assert tables["users"]["treatment_sensitivity"].nunique() > 100
    capacity = tables["city_hour_capacity"].assign(
        hour=lambda frame: frame["hour_ts"].dt.hour
    )
    peak = capacity.loc[capacity["hour"].between(18, 21), "utilization"].mean()
    overnight = capacity.loc[capacity["hour"].between(2, 5), "utilization"].mean()
    assert peak > overnight


def test_relationships_do_not_create_orphan_events() -> None:
    tables = generate_marketplace(seed=11, n_users=100, days=14)
    user_ids = set(tables["users"]["user_id"])
    merchant_ids = set(tables["merchants"]["merchant_id"])
    exposure_ids = set(tables["exposures"]["exposure_id"])
    order_ids = set(tables["orders"]["order_id"])

    assert set(tables["sessions"]["user_id"]).issubset(user_ids)
    assert set(tables["orders"]["user_id"]).issubset(user_ids)
    assert set(tables["orders"]["merchant_id"]).issubset(merchant_ids)
    assert set(tables["redemptions"]["exposure_id"]).issubset(exposure_ids)
    assert set(tables["cancellations"]["order_id"]).issubset(order_ids)
    assert set(tables["refunds"]["order_id"]).issubset(order_ids)


def test_events_use_timezone_aware_timestamps() -> None:
    tables = generate_marketplace(seed=12, n_users=80, days=14)
    for table_name in ("users", "sessions", "orders", "exposures", "redemptions"):
        timestamp_columns = [
            column
            for column in tables[table_name].columns
            if column.endswith("_ts")
        ]
        for column in timestamp_columns:
            assert str(tables[table_name][column].dtype).startswith("datetime64[ns, UTC]")


def test_write_build_outputs_csv_tables_and_manifest(tmp_path: Path) -> None:
    written = write_marketplace_data(
        output_dir=tmp_path, seed=5, n_users=40, days=7
    )

    assert set(written) == set(TABLE_NAMES)
    assert all(path.is_file() and path.suffix == ".csv" for path in written.values())
    assert (tmp_path / "manifest.json").is_file()


def test_schema_and_dictionary_cover_every_m2_table() -> None:
    schema = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
    dictionary = (ROOT / "docs/data_dictionary.md").read_text(encoding="utf-8")

    for table_name in TABLE_NAMES:
        assert f"CREATE TABLE {table_name}" in schema
        assert f"| `{table_name}` |" in dictionary
