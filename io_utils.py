"""I/O utilities for saving and loading tables, enforcing schema order, determinism, and ground-truth isolation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from schema import TABLE_DEFINITIONS

GROUND_TRUTH_COLUMNS: List[str] = [
    "gt_id",
    "scenario_id",
    "scenario_type",
    "label",
    "issue_type",
    "entity_type",
    "entity_id",
    "account_id",
    "trigger_txn_id",
    "expected_rule_id",
    "expected_alert",
    "expected_decision",
    "notes",
]

def compute_sha256(file_path: str | Path) -> str:
    """Compute deterministic SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def ensure_dir(dir_path: str | Path) -> Path:
    p = Path(dir_path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def save_table(df: pd.DataFrame | List[Dict[str, Any]], table_name: str, out_dir: str = "output") -> Path:
    """Save a table to output/data/{table_name}.csv adhering to strict determinism rules."""
    if table_name not in TABLE_DEFINITIONS:
        raise ValueError(f"Unknown table '{table_name}'. Not defined in schema.")

    if isinstance(df, list):
        df = pd.DataFrame(df)

    tdef = TABLE_DEFINITIONS[table_name]
    expected_cols = [f.name for f in tdef.fields]

    # Check for missing columns
    for col in expected_cols:
        if col not in df.columns:
            df[col] = None

    # Reorder columns to exact schema order
    out_df = df[expected_cols].copy()

    # Sort deterministically by primary key
    pk_cols = tdef.primary_key
    if pk_cols:
        out_df = out_df.sort_values(by=pk_cols).reset_index(drop=True)

    data_dir = ensure_dir(Path(out_dir) / "data")
    csv_path = data_dir / f"{table_name}.csv"

    # Strict formatting: LF endings, float format %.2f, empty string for NA
    out_df.to_csv(
        csv_path,
        index=False,
        lineterminator="\n",
        float_format="%.2f",
        na_rep="",
    )
    return csv_path

def load_table(table_name: str, out_dir: str = "output") -> pd.DataFrame:
    """Load a table strictly from output/data/{table_name}.csv."""
    if table_name not in TABLE_DEFINITIONS:
        raise ValueError(f"Unknown table '{table_name}'. Not defined in schema.")

    csv_path = Path(out_dir) / "data" / f"{table_name}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Table file not found: {csv_path}")

    # Read all columns as object/string first or parse appropriate types to preserve fidelity
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    return df

def save_ground_truth(df: pd.DataFrame | List[Dict[str, Any]], out_dir: str = "output") -> Tuple[Path, Path]:
    """Save ground truth to output/ground_truth/ground_truth.csv and .json."""
    if isinstance(df, list):
        df = pd.DataFrame(df)
    gt_dir = ensure_dir(Path(out_dir) / "ground_truth")
    for col in GROUND_TRUTH_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    out_df = df[GROUND_TRUTH_COLUMNS].copy()
    if "gt_id" in out_df.columns:
        out_df = out_df.sort_values(by=["gt_id"]).reset_index(drop=True)

    csv_path = gt_dir / "ground_truth.csv"
    out_df.to_csv(
        csv_path,
        index=False,
        lineterminator="\n",
        na_rep="",
    )

    json_path = gt_dir / "ground_truth.json"
    records = out_df.to_dict(orient="records")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, sort_keys=True)

    return csv_path, json_path

def load_ground_truth(out_dir: str = "output") -> pd.DataFrame:
    """Load ground truth with security guard to prevent data leakage into rules engine."""
    if os.environ.get("ALLOW_GT") != "1":
        raise PermissionError(
            "Access to ground truth is guarded. Environment variable ALLOW_GT=1 must be set. "
            "Rules engine and data generators must never access ground truth directly."
        )

    csv_path = Path(out_dir) / "ground_truth" / "ground_truth.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {csv_path}")

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    return df

