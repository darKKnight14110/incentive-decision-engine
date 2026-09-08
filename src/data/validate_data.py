"""Data-quality checks for the generated marketplace source tables."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.data.build_features import execute_sql_assets, load_marketplace_tables


def find_data_quality_issues(
    raw_dir: str | Path = "data/raw", sql_dir: str | Path = "sql"
) -> pd.DataFrame:
    """Return detected source defects without mutating or silently repairing data."""
    connection = duckdb.connect()
    try:
        load_marketplace_tables(connection, raw_dir)
        execute_sql_assets(connection, sql_dir)
        return connection.sql(
            "SELECT * FROM data_quality_issues ORDER BY issue_type"
        ).df()
    finally:
        connection.close()
