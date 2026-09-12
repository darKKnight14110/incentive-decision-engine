"""Criteo uplift dataset download, validation, and deterministic partitioning.

The raw dataset is intentionally never committed.  All public functions also
work with an in-memory smoke frame, which keeps CI and ``make build`` offline.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.request import urlopen

import numpy as np
import pandas as pd

FEATURE_COLUMNS = [f"f{i}" for i in range(12)]
REQUIRED_COLUMNS = FEATURE_COLUMNS + ["treatment", "exposure", "visit", "conversion"]
DEFAULT_URL = "http://go.criteo.net/criteo-research-uplift-v2.1.csv.gz"


@dataclass(frozen=True)
class CriteoDataset:
    """Validated Criteo rows plus reproducible train/validation/test indexes."""

    frame: pd.DataFrame
    train_index: np.ndarray
    validation_index: np.ndarray
    test_index: np.ndarray
    manifest: dict[str, object]


def validate_criteo_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and return a normalized Criteo frame."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    extra = sorted(set(frame.columns) - set(REQUIRED_COLUMNS))
    if missing:
        raise ValueError(f"Criteo frame missing columns: {missing}")
    if extra:
        raise ValueError(f"Unexpected Criteo columns: {extra}")
    clean = frame[REQUIRED_COLUMNS].copy()
    if clean.isna().any().any():
        raise ValueError("Criteo frame contains null values")
    for column in REQUIRED_COLUMNS[12:]:
        values = set(pd.unique(clean[column]))
        if not values <= {0, 1, False, True}:
            raise ValueError(f"{column} must be binary, got {sorted(values)}")
        clean[column] = clean[column].astype(np.int8)
    for column in FEATURE_COLUMNS:
        clean[column] = pd.to_numeric(clean[column], errors="raise").astype(np.float32)
    return clean


def smoke_criteo(n_rows: int = 12_000, seed: int = 2025) -> pd.DataFrame:
    """Create a deterministic Criteo-shaped frame for offline development."""
    if n_rows < 100:
        raise ValueError("n_rows must be at least 100")
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n_rows, 12)).astype(np.float32)
    propensity = 1 / (1 + np.exp(-0.25 * x[:, 0]))
    treatment = rng.binomial(1, np.clip(0.85 + 0.02 * (propensity - 0.5), 0.05, 0.95))
    baseline = 0.015 + 0.01 / (1 + np.exp(-x[:, 1]))
    uplift = 0.004 * np.tanh(x[:, 2]) - 0.001 * (x[:, 3] > 1)
    conversion = rng.binomial(1, np.clip(baseline + treatment * uplift, 0.0001, 0.5))
    visit = np.maximum(conversion, rng.binomial(1, np.clip(0.04 + 0.01 * treatment, 0, 0.9)))
    exposure = rng.binomial(1, np.clip(0.8 * treatment + 0.02, 0, 1))
    return validate_criteo_frame(pd.DataFrame({**{f"f{i}": x[:, i] for i in range(12)},
        "treatment": treatment, "exposure": exposure, "visit": visit, "conversion": conversion}))


def _stratified_indexes(frame: pd.DataFrame, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    strata = frame["treatment"].astype(str) + frame["conversion"].astype(str)
    rng = np.random.default_rng(seed)
    train_parts, validation_parts, test_parts = [], [], []
    for _, group in frame.groupby(strata, sort=True):
        indexes = rng.permutation(group.index.to_numpy())
        n = len(indexes)
        n_train = max(1, int(round(n * .60)))
        n_validation = max(0, int(round(n * .20)))
        if n_train + n_validation > n: n_validation = max(0, n - n_train)
        train_parts.append(indexes[:n_train]); validation_parts.append(indexes[n_train:n_train+n_validation]); test_parts.append(indexes[n_train+n_validation:])
    return np.sort(np.concatenate(train_parts)), np.sort(np.concatenate(validation_parts)), np.sort(np.concatenate(test_parts))


def partition_criteo(frame: pd.DataFrame, seed: int = 2025) -> CriteoDataset:
    clean = validate_criteo_frame(frame).reset_index(drop=True)
    train, validation, test = _stratified_indexes(clean, seed)
    return CriteoDataset(clean, train, validation, test, {"seed": seed, "rows": len(clean)})


def iter_criteo(path: str | Path, chunksize: int = 250_000) -> Iterator[pd.DataFrame]:
    """Stream a local CSV or gzip CSV without loading all rows at once."""
    source = Path(path)
    compression = "gzip" if source.suffix == ".gz" else None
    for chunk in pd.read_csv(source, compression=compression, chunksize=chunksize):
        yield validate_criteo_frame(chunk)


def download_criteo(download_dir: str | Path, url: str = DEFAULT_URL, timeout: int = 120) -> Path:
    """Download the public gzip file and write a provenance manifest."""
    target = Path(download_dir)
    target.mkdir(parents=True, exist_ok=True)
    archive = target / Path(url).name
    digest = hashlib.sha256()
    with urlopen(url, timeout=timeout) as response, archive.open("wb") as output:
        while block := response.read(1024 * 1024):
            digest.update(block)
            output.write(block)
    manifest = {"url": url, "archive": archive.name, "sha256": digest.hexdigest(), "citation": "Diemert et al. (2018), Criteo Uplift Prediction Dataset"}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return archive


def load_criteo(path: str | Path, seed: int = 2025, max_rows: int | None = None) -> CriteoDataset:
    """Load a local Criteo CSV, optionally truncating deterministically for smoke runs."""
    chunks = []
    remaining = max_rows
    for chunk in iter_criteo(path):
        if remaining is not None:
            chunks.append(chunk.iloc[:remaining])
            remaining -= len(chunks[-1])
            if remaining <= 0:
                break
        else:
            chunks.append(chunk)
    if not chunks:
        raise ValueError(f"No rows found in {path}")
    return partition_criteo(pd.concat(chunks, ignore_index=True), seed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-dir", type=Path, default=Path("data/raw/criteo"))
    args = parser.parse_args()
    print(download_criteo(args.download_dir))
