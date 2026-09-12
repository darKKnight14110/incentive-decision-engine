"""Criteo uplift dataset download, validation, and deterministic partitioning.

The raw dataset is intentionally never committed.  All public functions also
work with an in-memory smoke frame, which keeps CI and ``make build`` offline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.request import urlopen

import numpy as np
import pandas as pd

FEATURE_COLUMNS = [f"f{i}" for i in range(12)]
REQUIRED_COLUMNS = FEATURE_COLUMNS + ["treatment", "exposure", "visit", "conversion"]
SOURCE_URL = "https://ailab.criteo.com/criteo-uplift-prediction-dataset/"
DEFAULT_URL = "https://go.criteo.net/criteo-research-uplift-v2.1.csv.gz"
RESOLVED_URL = "https://criteostorage.blob.core.windows.net/criteo-research-datasets/criteo-uplift-v2.1.csv.gz"
CITATION = "Diemert et al. (2018), Criteo Uplift Prediction Dataset"
LICENSE_STATUS = "CC BY-NC-SA 4.0; non-commercial use with attribution and ShareAlike terms (Criteo dataset webpage)."


@dataclass(frozen=True)
class DatasetManifest:
    """Portable provenance contract for a validated Criteo archive."""

    source: str
    resolved_url: str
    sha256: str
    schema: dict[str, str]
    row_count: int
    citation: str
    license_status: str
    retrieved_at_utc: str | None = None
    compressed_size_bytes: int | None = None


@dataclass(frozen=True)
class SplitManifest:
    """Deterministic split metadata independent of machine-local paths."""

    seed: int
    strata: list[str]
    train_rows: int
    validation_rows: int
    test_rows: int
    input_hash: str


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
    split_manifest = SplitManifest(
        seed=seed,
        strata=sorted((clean.treatment.astype(str) + clean.conversion.astype(str)).unique().tolist()),
        train_rows=len(train),
        validation_rows=len(validation),
        test_rows=len(test),
        input_hash=_frame_hash(clean),
    )
    return CriteoDataset(clean, train, validation, test, {"seed": seed, "rows": len(clean), "split": split_manifest.__dict__})


def _frame_hash(frame: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    digest.update(",".join(frame.columns).encode("utf-8"))
    digest.update(pd.util.hash_pandas_object(frame, index=True).to_numpy(dtype="uint64").tobytes())
    return digest.hexdigest()


def _schema() -> dict[str, str]:
    return {column: ("float32" if column in FEATURE_COLUMNS else "int8") for column in REQUIRED_COLUMNS}


def scan_criteo(path: str | Path, chunksize: int = 250_000) -> DatasetManifest:
    """Validate an archive in bounded chunks and return complete provenance."""

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    rows = 0
    for chunk in iter_criteo(source, chunksize=chunksize):
        rows += len(chunk)
    return DatasetManifest(
        source=SOURCE_URL,
        resolved_url="",
        sha256=_sha256_file(source),
        schema=_schema(),
        row_count=rows,
        citation=CITATION,
        license_status=LICENSE_STATUS,
        compressed_size_bytes=source.stat().st_size,
    )


def iter_criteo(path: str | Path, chunksize: int = 250_000) -> Iterator[pd.DataFrame]:
    """Stream a local CSV or gzip CSV without loading all rows at once."""
    source = Path(path)
    compression = "gzip" if source.suffix == ".gz" else None
    for chunk in pd.read_csv(source, compression=compression, chunksize=chunksize):
        yield validate_criteo_frame(chunk)


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_criteo(
    download_dir: str | Path,
    url: str = DEFAULT_URL,
    timeout: int = 120,
    minimum_free_bytes: int = 512 * 1024 * 1024,
) -> Path:
    """Download the public gzip file atomically and write a provenance manifest.

    The short ``go.criteo.net`` URL is the published entry point and normally
    redirects to Criteo's Azure blob.  The resolved endpoint is attempted as a
    fallback because redirects can be blocked by corporate proxies.  No mirror
    or unverified copy is ever used.
    """
    target = Path(download_dir)
    target.mkdir(parents=True, exist_ok=True)
    archive = target / Path(url).name
    partial = archive.with_suffix(archive.suffix + ".part")
    if archive.exists():
        manifest_path = target / "manifest.json"
        if manifest_path.exists():
            return archive
        raise FileExistsError(f"refusing to overwrite existing archive without a manifest: {archive}")
    free_bytes = shutil.disk_usage(target).free
    if free_bytes < int(minimum_free_bytes):
        raise OSError(
            f"insufficient free disk for Criteo download: {free_bytes} bytes available, "
            f"{minimum_free_bytes} required; choose a volume with more space"
        )
    if partial.exists():
        partial.unlink()
    attempted = [url]
    if url != RESOLVED_URL and "go.criteo.net" in url:
        attempted.append(RESOLVED_URL)
    last_error: Exception | None = None
    resolved_url = ""
    digest = hashlib.sha256()
    for candidate_url in attempted:
        digest = hashlib.sha256()
        try:
            with urlopen(candidate_url, timeout=timeout) as response, partial.open("wb") as output:
                while block := response.read(1024 * 1024):
                    digest.update(block)
                    output.write(block)
                resolved_url = response.geturl()
            partial.replace(archive)
            break
        except Exception as error:
            last_error = error
            if partial.exists():
                partial.unlink()
        except KeyboardInterrupt:
            if partial.exists():
                partial.unlink()
            raise
    else:
        failure = {
            "source": SOURCE_URL,
            "requested_urls": attempted,
            "error": repr(last_error),
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        (target / "download_error.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
        raise RuntimeError(
            "Criteo download failed for the published endpoint and its official resolved storage URL; "
            "see data/raw/criteo/download_error.json. No partial archive was retained."
        ) from last_error
    scanned = scan_criteo(archive)
    manifest = DatasetManifest(
        source=scanned.source,
        resolved_url=resolved_url,
        sha256=digest.hexdigest(),
        schema=scanned.schema,
        row_count=scanned.row_count,
        citation=CITATION,
        license_status=LICENSE_STATUS,
        retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
        compressed_size_bytes=archive.stat().st_size,
    )
    (target / "manifest.json").write_text(json.dumps(manifest.__dict__, indent=2), encoding="utf-8")
    return archive


def write_criteo_partitions(
    path: str | Path,
    output_dir: str | Path,
    seed: int = 2025,
    chunksize: int = 250_000,
    use_duckdb: bool = True,
) -> dict[str, object]:
    """Write deterministic, compressed Parquet chunks without full-frame loading.

    A seeded row hash is applied within treatment/conversion strata. Each split
    is a directory of immutable parts, allowing bounded reads during model
    fitting and final-test scoring.
    """

    root = Path(output_dir)
    existing_manifest = root / "manifest.json"
    if existing_manifest.exists():
        try:
            cached = json.loads(existing_manifest.read_text(encoding="utf-8"))
            if (
                int(cached.get("seed", -1)) == int(seed)
                and cached.get("input_sha256") == _sha256_file(path)
                and bool(cached.get("coverage_verified"))
                and sum(dict(cached.get("counts", {})).values()) > 0
            ):
                return cached
        except (OSError, ValueError, TypeError):
            pass
    if use_duckdb:
        try:
            return _write_criteo_partitions_duckdb(path, output_dir, seed=seed)
        except ImportError:
            # The package declares DuckDB as a runtime dependency, but keeping
            # the bounded pandas implementation makes the loader usable in
            # minimal environments and preserves a clear fallback path.
            pass
    root.mkdir(parents=True, exist_ok=True)
    counts = {"train": 0, "validation": 0, "test": 0}
    parts = {name: 0 for name in counts}
    stratum_counts: dict[str, dict[str, int]] = {name: {} for name in counts}
    row_id = 0
    for chunk in iter_criteo(path, chunksize=chunksize):
        chunk = chunk.copy()
        ids = np.arange(row_id, row_id + len(chunk), dtype=np.uint64)
        row_id += len(chunk)
        strata = chunk.treatment.astype(str) + chunk.conversion.astype(str)
        # Hashing a stable row id and stratum prevents order-dependent splits
        # while preserving treatment/outcome composition in expectation.
        keys = pd.util.hash_pandas_object(
            pd.DataFrame({"row_id": ids, "stratum": strata.to_numpy()}), index=False
        ).to_numpy(dtype="uint64")
        bucket = (keys ^ np.uint64(seed)) % np.uint64(100)
        labels = np.where(bucket < 60, "train", np.where(bucket < 80, "validation", "test"))
        for label in counts:
            subset = chunk.loc[labels == label].copy()
            if subset.empty:
                continue
            target = root / label
            target.mkdir(parents=True, exist_ok=True)
            output = target / f"part-{parts[label]:06d}.parquet"
            subset.to_parquet(output, index=False, compression="zstd")
            parts[label] += 1
            counts[label] += len(subset)
            for stratum, count in strata.loc[labels == label].value_counts().items():
                stratum_counts[label][str(stratum)] = stratum_counts[label].get(str(stratum), 0) + int(count)
    manifest = {
        "seed": seed,
        "input": str(path),
        "input_sha256": _sha256_file(path),
        "schema": _schema(),
        "counts": counts,
        "parts": parts,
        "fractions": {name: value / max(row_id, 1) for name, value in counts.items()},
        "stratum_counts": stratum_counts,
        "coverage_verified": sum(counts.values()) == row_id,
        "exclusive_verified": True,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _write_criteo_partitions_duckdb(
    path: str | Path,
    output_dir: str | Path,
    seed: int = 2025,
) -> dict[str, object]:
    """Ingest a compressed CSV through DuckDB and emit one Parquet per split."""

    import duckdb

    source = Path(path)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    for split in ("train", "validation", "test"):
        (root / split).mkdir(parents=True, exist_ok=True)
    escaped = source.resolve().as_posix().replace("'", "''")
    connection = duckdb.connect()
    try:
        connection.execute(
            "CREATE TEMP TABLE criteo_source AS "
            "SELECT row_number() OVER () - 1 AS row_id, * "
            f"FROM read_csv_auto('{escaped}', header=true, compression='gzip')"
        )
        columns = ", ".join(f'"{column}"' for column in REQUIRED_COLUMNS)
        # Hashing the stable row id and treatment/outcome stratum preserves
        # composition in expectation while avoiding a pandas full-frame join.
        bucket = f"hash(row_id + {int(seed)}, treatment, conversion) % 100"
        labels = {
            "train": f"({bucket}) < 60",
            "validation": f"({bucket}) >= 60 AND ({bucket}) < 80",
            "test": f"({bucket}) >= 80",
        }
        counts: dict[str, int] = {}
        stratum_counts: dict[str, dict[str, int]] = {}
        for split, predicate in labels.items():
            target = root / split / "part-000000.parquet"
            connection.execute(
                f"COPY (SELECT {columns} FROM criteo_source WHERE {predicate}) "
                f"TO '{target.resolve().as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            counts[split] = int(connection.execute(f"SELECT count(*) FROM criteo_source WHERE {predicate}").fetchone()[0])
            strata = connection.execute(
                f"SELECT CAST(treatment AS VARCHAR) || CAST(conversion AS VARCHAR) AS stratum, count(*) "
                f"FROM criteo_source WHERE {predicate} GROUP BY 1 ORDER BY 1"
            ).fetchall()
            stratum_counts[split] = {str(row[0]): int(row[1]) for row in strata}
        row_count = int(connection.execute("SELECT count(*) FROM criteo_source").fetchone()[0])
    finally:
        connection.close()
    manifest = {
        "seed": int(seed),
        "input": str(source),
        "input_sha256": _sha256_file(source),
        "schema": _schema(),
        "counts": counts,
        "parts": {split: 1 for split in labels},
        "fractions": {name: value / max(row_count, 1) for name, value in counts.items()},
        "stratum_counts": stratum_counts,
        "coverage_verified": sum(counts.values()) == row_count,
        "exclusive_verified": True,
        "ingestion_engine": "duckdb",
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def iter_partition(path: str | Path, split: str, chunksize: int = 250_000) -> Iterator[pd.DataFrame]:
    """Yield validated rows from a split-partition directory."""

    root = Path(path) / split
    files = sorted(root.glob("part-*.parquet"))
    if not files:
        raise FileNotFoundError(f"no partition files found for split={split}: {root}")
    for file in files:
        frame = pd.read_parquet(file)
        for start in range(0, len(frame), chunksize):
            yield validate_criteo_frame(frame.iloc[start : start + chunksize])


def load_partition(
    path: str | Path,
    split: str,
    max_rows: int | None = None,
    seed: int = 2025,
) -> pd.DataFrame:
    """Load a deterministic bounded sample from a Parquet split.

    DuckDB orders by a stable row-hash before applying ``LIMIT``. This avoids
    file-order bias in datasets whose first rows can be nearly single-arm.
    """

    if max_rows is not None:
        try:
            import duckdb

            root = Path(path) / split
            files = sorted(root.glob("part-*.parquet"))
            if not files:
                raise FileNotFoundError(f"no partition files found for split={split}: {root}")
            escaped = (root / "part-*.parquet").resolve().as_posix().replace("'", "''")
            columns = ", ".join(f'"{column}"' for column in REQUIRED_COLUMNS)
            connection = duckdb.connect()
            try:
                frame = connection.execute(
                    f"SELECT {columns} FROM (SELECT *, hash(row_number() OVER () + {int(seed)}) AS _sample_order "
                    f"FROM read_parquet('{escaped}')) ORDER BY _sample_order LIMIT {int(max_rows)}"
                ).df()
            finally:
                connection.close()
            return validate_criteo_frame(frame)
        except ImportError:
            pass

    chunks: list[pd.DataFrame] = []
    remaining = max_rows
    for chunk in iter_partition(path, split):
        if remaining is None:
            chunks.append(chunk)
            continue
        take = chunk.iloc[:remaining]
        if not take.empty:
            chunks.append(take)
        remaining -= len(take)
        if remaining <= 0:
            break
    if not chunks:
        raise ValueError(f"no rows found in partition split={split}")
    return pd.concat(chunks, ignore_index=True)


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
