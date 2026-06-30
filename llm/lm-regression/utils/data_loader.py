"""
Data loading utilities for the Code-Regression dataset.

Handles downloading Parquet files from HuggingFace, loading partitions
(APPS, CDSS, KBSS), parsing metadata, and validation-mode sampling.
"""

import ast
import os
from pathlib import Path

import pandas as pd
from huggingface_hub import hf_hub_download, list_repo_files
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO_ID = "akhauriyash/Code-Regression"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VALID_SPACES = {"APPS", "CDSS", "KBSS"}
VALIDATION_SAMPLE_SIZE = 500  # rows per partition in validation mode


def is_validation_mode() -> bool:
    """Return True unless CODE_REGRESSION_FULL=1 is set."""
    return os.environ.get("CODE_REGRESSION_FULL", "0") != "1"


def print_mode_banner(validation_mode: bool) -> None:
    """Print a human-readable banner about the current run mode."""
    if validation_mode:
        print(
            f"[VALIDATION] VALIDATION_MODE = True\n"
            f"   Running with limited data (~{VALIDATION_SAMPLE_SIZE} rows/partition).\n"
            f"   Set environment variable CODE_REGRESSION_FULL=1 for a full run."
        )
    else:
        print("[FULL] FULL MODE -- using complete dataset. This may take a while.")


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_dataset(force: bool = False) -> list[Path]:
    """
    Download all Parquet files from the HuggingFace repo into DATA_DIR.

    Parameters
    ----------
    force : bool
        Re-download even if files already exist locally.

    Returns
    -------
    list[Path]
        Paths to the downloaded Parquet files.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # List remote parquet files
    all_files = list_repo_files(REPO_ID, repo_type="dataset")
    parquet_files = [f for f in all_files if f.endswith(".parquet")]

    if not parquet_files:
        raise RuntimeError(
            f"No Parquet files found in {REPO_ID}. "
            "Check the dataset URL and your network connection."
        )

    downloaded = []
    for remote_path in tqdm(parquet_files, desc="Downloading parquet files"):
        local_path = DATA_DIR / Path(remote_path).name

        if local_path.exists() and not force:
            print(f"  [OK] Already cached: {local_path.name}")
            downloaded.append(local_path)
            continue

        hf_hub_download(
            repo_id=REPO_ID,
            filename=remote_path,
            repo_type="dataset",
            local_dir=str(DATA_DIR),
        )
        # hf_hub_download may create subdirectories; find the actual file
        actual = DATA_DIR / remote_path
        if actual.exists() and actual != local_path:
            actual.rename(local_path)

        downloaded.append(local_path)
        print(f"  [DL] Downloaded: {local_path.name}")

    return downloaded


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_full_dataset(validation_mode: bool | None = None) -> pd.DataFrame:
    """
    Load the full dataset from all Parquet files in DATA_DIR.

    Parameters
    ----------
    validation_mode : bool or None
        If None, auto-detect from environment. If True, sample per partition.

    Returns
    -------
    pd.DataFrame
    """
    if validation_mode is None:
        validation_mode = is_validation_mode()

    parquet_files = sorted(DATA_DIR.rglob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(
            f"No Parquet files found in {DATA_DIR}. "
            "Run download_dataset() first."
        )

    dfs = []
    for pf in tqdm(parquet_files, desc="Loading parquet files"):
        dfs.append(pd.read_parquet(pf))

    df = pd.concat(dfs, ignore_index=True)

    if validation_mode:
        sampled_parts = []
        for space in VALID_SPACES:
            part = df[df["space"] == space]
            n = min(len(part), VALIDATION_SAMPLE_SIZE)
            sampled_parts.append(part.sample(n=n, random_state=42))
        df = pd.concat(sampled_parts, ignore_index=True)

    return df


def load_partition(
    space: str,
    validation_mode: bool | None = None,
    sample_size: int | None = None,
) -> pd.DataFrame:
    """
    Load a single partition (APPS, CDSS, or KBSS) from the Parquet files.

    Parameters
    ----------
    space : str
        One of 'APPS', 'CDSS', 'KBSS'.
    validation_mode : bool or None
        If None, auto-detect from environment.
    sample_size : int or None
        Override the default sample size for validation mode.

    Returns
    -------
    pd.DataFrame
    """
    if space not in VALID_SPACES:
        raise ValueError(f"Invalid space '{space}'. Must be one of {VALID_SPACES}")

    if validation_mode is None:
        validation_mode = is_validation_mode()

    parquet_files = sorted(DATA_DIR.rglob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(
            f"No Parquet files found in {DATA_DIR}. "
            "Run download_dataset() first."
        )

    dfs = []
    for pf in tqdm(parquet_files, desc=f"Loading {space} partition", leave=False):
        df = pd.read_parquet(pf)
        part = df[df["space"] == space]
        if len(part) > 0:
            dfs.append(part)

    if not dfs:
        raise ValueError(f"No rows found for space='{space}' in the dataset.")

    result = pd.concat(dfs, ignore_index=True)

    if validation_mode:
        n = sample_size or VALIDATION_SAMPLE_SIZE
        n = min(len(result), n)
        result = result.sample(n=n, random_state=42)
        result = result.reset_index(drop=True)

    return result


# ---------------------------------------------------------------------------
# Metadata parsing
# ---------------------------------------------------------------------------

def parse_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse the stringified metadata column into a proper dict column,
    then expand selected keys into new columns.

    The metadata column contains Python-dict-like strings that can be
    safely evaluated with ast.literal_eval.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain a 'metadata' column.

    Returns
    -------
    pd.DataFrame
        A copy with 'metadata_dict' column and any extractable keys
        promoted to top-level columns.
    """
    df = df.copy()

    def _safe_parse(s):
        if pd.isna(s) or s == "":
            return {}
        try:
            return ast.literal_eval(str(s))
        except (ValueError, SyntaxError):
            return {}

    df["metadata_dict"] = df["metadata"].apply(_safe_parse)

    # Extract common keys when present
    known_keys = [
        "cpu_time", "memory", "code_size", "status", "language",
        "stddev_ms", "s_id", "p_id",
    ]
    for key in known_keys:
        values = df["metadata_dict"].apply(lambda d, k=key: d.get(k))
        if values.notna().any():
            df[f"meta_{key}"] = values

    return df


# ---------------------------------------------------------------------------
# Schema audit helpers
# ---------------------------------------------------------------------------

def audit_schema(df: pd.DataFrame) -> None:
    """Print a formatted schema audit of the dataset."""
    print("=" * 70)
    print("DATASET SCHEMA AUDIT")
    print("=" * 70)
    print(f"\nTotal rows: {len(df):,}")
    print(f"Columns: {list(df.columns)}")
    print(f"\nDtypes:\n{df.dtypes.to_string()}")

    print("\n--- Partition Counts ---")
    if "space" in df.columns:
        counts = df["space"].value_counts()
        for space, count in counts.items():
            print(f"  {space}: {count:,} rows")

    print("\n--- metric_type Distribution ---")
    if "metric_type" in df.columns:
        mt_counts = df["metric_type"].value_counts()
        for mt, count in mt_counts.items():
            print(f"  {mt}: {count:,} rows")

    print("\n--- val_accuracy Summary ---")
    if "val_accuracy" in df.columns:
        print(df["val_accuracy"].describe().to_string())

    print("\n--- target_metric Unique Values ---")
    if "target_metric" in df.columns:
        print(f"  {df['target_metric'].unique()}")

    print("=" * 70)
