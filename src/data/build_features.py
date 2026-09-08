"""Build DuckDB analytics views and a point-in-time eligible-user table."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Mapping

import duckdb
import pandas as pd

from src.data.generate_marketplace import TABLE_NAMES, write_marketplace_data

SQL_ASSETS = (
    "product_metrics.sql",
    "retention_cohorts.sql",
    "user_features.sql",
    "experiment_metrics.sql",
    "data_quality.sql",
)


def _read_table(path: Path) -> pd.DataFrame:
    """Read a generated CSV and normalize all timestamp columns to UTC."""
    frame = pd.read_csv(path)
    for column in frame.columns:
        if column.endswith("_ts"):
            frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame


def register_marketplace_tables(
    connection: duckdb.DuckDBPyConnection,
    tables: Mapping[str, pd.DataFrame],
) -> None:
    """Register DataFrames as DuckDB tables using the M2 table names."""
    missing = set(TABLE_NAMES) - set(tables)
    if missing:
        raise ValueError(f"missing marketplace tables: {sorted(missing)}")
    for table_name in TABLE_NAMES:
        frame = tables[table_name]
        if not isinstance(frame, pd.DataFrame):
            raise TypeError(f"table {table_name!r} must be a pandas DataFrame")
        registered_name = f"_input_{table_name}"
        connection.register(registered_name, frame)
        connection.execute(
            f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM "{registered_name}"'
        )
        connection.unregister(registered_name)


def load_marketplace_tables(
    connection: duckdb.DuckDBPyConnection, raw_dir: str | Path
) -> None:
    """Load the generated CSV tables from a directory into DuckDB."""
    source = Path(raw_dir)
    missing = [table for table in TABLE_NAMES if not (source / f"{table}.csv").is_file()]
    if missing:
        raise FileNotFoundError(f"missing generated tables in {source}: {missing}")
    register_marketplace_tables(
        connection,
        {table: _read_table(source / f"{table}.csv") for table in TABLE_NAMES},
    )


def execute_sql_assets(
    connection: duckdb.DuckDBPyConnection, sql_dir: str | Path
) -> None:
    """Create all analytics views in dependency order."""
    root = Path(sql_dir)
    for asset_name in SQL_ASSETS:
        connection.execute((root / asset_name).read_text(encoding="utf-8"))


def build_feature_frame(
    tables: Mapping[str, pd.DataFrame],
    sql_dir: str | Path = "sql",
) -> pd.DataFrame:
    """Return eligible users after running the complete SQL analytics layer."""
    connection = duckdb.connect()
    try:
        register_marketplace_tables(connection, tables)
        execute_sql_assets(connection, sql_dir)
        return connection.sql(
            "SELECT * FROM eligible_users ORDER BY user_id, decision_ts"
        ).df()
    finally:
        connection.close()


def build_features(
    raw_dir: str | Path = "data/raw",
    output_path: str | Path = "data/processed/eligible_users.parquet",
    sql_dir: str | Path = "sql",
) -> pd.DataFrame:
    """Rebuild the point-in-time feature table from raw CSV tables."""
    connection = duckdb.connect()
    try:
        load_marketplace_tables(connection, raw_dir)
        execute_sql_assets(connection, sql_dir)
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        connection.execute(
            "COPY (SELECT * FROM eligible_users ORDER BY user_id, decision_ts) "
            "TO ? (FORMAT PARQUET)",
            [str(target)],
        )
        return connection.sql(
            "SELECT * FROM eligible_users ORDER BY user_id, decision_ts"
        ).df()
    finally:
        connection.close()


def build_quality_report(
    raw_dir: str | Path = "data/raw",
    output_path: str | Path = "data/processed/data_quality_issues.csv",
    sql_dir: str | Path = "sql",
) -> pd.DataFrame:
    """Write the non-destructive raw-data quality report used by the build."""
    connection = duckdb.connect()
    try:
        load_marketplace_tables(connection, raw_dir)
        execute_sql_assets(connection, sql_dir)
        report = connection.sql(
            "SELECT * FROM data_quality_issues ORDER BY issue_type"
        ).df()
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(target, index=False)
        return report
    finally:
        connection.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--output-path",
        type=Path,
        default=Path("data/processed/eligible_users.parquet"),
    )
    parser.add_argument("--sql-dir", type=Path, default=Path("sql"))
    parser.add_argument("--quality-report", type=Path)
    parser.add_argument("--generate-if-missing", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse_args()
    if arguments.generate_if_missing and not arguments.raw_dir.exists():
        write_marketplace_data(arguments.raw_dir)
    result = build_features(
        raw_dir=arguments.raw_dir,
        output_path=arguments.output_path,
        sql_dir=arguments.sql_dir,
    )
    print(f"eligible_users: {len(result)} rows -> {arguments.output_path}")
    if arguments.quality_report:
        report = build_quality_report(
            raw_dir=arguments.raw_dir,
            output_path=arguments.quality_report,
            sql_dir=arguments.sql_dir,
        )
        print(f"quality_issues: {len(report)} rows -> {arguments.quality_report}")
