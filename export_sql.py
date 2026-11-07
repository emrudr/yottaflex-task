"""Stage 2c / Export: Generate seed.sql with DDL, constraints, and inserts, and verify via in-memory SQLite."""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from io_utils import ensure_dir, load_table
from schema import TABLE_DEFINITIONS, TableDef

TABLE_INSERT_ORDER: List[str] = [
    "customers",
    "merchants",
    "analysts",
    "risk_rules",
    "devices",
    "accounts",
    "account_status_events",
    "account_devices",
    "cases",
    "transfer_links",
    "transactions",
    "alerts",
    "alert_evidence",
    "alert_score_components",
    "analyst_actions",
]

def map_sql_type(data_type: str) -> str:
    dt = data_type.upper()
    if dt.startswith("VARCHAR") or dt in ("DATE", "TIMESTAMP", "TEXT"):
        return "TEXT"
    elif dt.startswith("DECIMAL") or dt in ("REAL", "FLOAT"):
        return "REAL"
    elif dt in ("INTEGER", "BOOLEAN", "INT"):
        return "INTEGER"
    return "TEXT"

def generate_ddl(tdef: TableDef) -> str:
    lines = [f"CREATE TABLE IF NOT EXISTS {tdef.name} ("]
    col_defs = []

    for f in tdef.fields:
        col_type = map_sql_type(f.data_type)
        parts = [f"    {f.name} {col_type}"]
        if f.required and f.name not in tdef.primary_key:
            parts.append("NOT NULL")
        if f.unique and len(tdef.primary_key) == 1 and f.name == tdef.primary_key[0]:
            pass  # PK covers it
        elif f.unique:
            parts.append("UNIQUE")
        if f.allowed_values:
            vals = ", ".join(f"'{v}'" for v in f.allowed_values)
            parts.append(f"CHECK ({f.name} IN ({vals}))")
        col_defs.append(" ".join(parts))

    # Primary key
    pk_cols = ", ".join(tdef.primary_key)
    col_defs.append(f"    PRIMARY KEY ({pk_cols})")

    # Foreign keys (deferred for mutual / circular dependencies)
    for fk in tdef.foreign_keys:
        col_defs.append(
            f"    FOREIGN KEY ({fk.column}) REFERENCES {fk.target_table} ({fk.target_column}) DEFERRABLE INITIALLY DEFERRED"
        )

    lines.append(",\n".join(col_defs))
    lines.append(");")
    return "\n".join(lines)

def sql_quote(val: Any, data_type: str) -> str:
    if val is None or val == "" or pd.isna(val):
        return "NULL"
    dt = data_type.upper()
    if dt == "BOOLEAN":
        s = str(val).lower()
        return "1" if s in ("true", "1", "t") else "0"
    elif dt in ("INTEGER", "INT"):
        return str(int(float(val)))
    elif dt.startswith("DECIMAL") or dt in ("REAL", "FLOAT"):
        return f"{float(val):.2f}"
    else:
        # String escape single quotes
        escaped = str(val).replace("'", "''")
        return f"'{escaped}'"

def generate_seed_sql(out_dir: str = "output") -> Path:
    sql_dir = ensure_dir(Path(out_dir) / "sql")
    sql_file = sql_dir / "seed.sql"

    print(f"[*] Exporting database schema and data to {sql_file}...")

    lines = [
        "-- Synthetic Risk-Alert Prioritization Pipeline Seed SQL",
        "-- Deterministic export from CSV storage",
        "PRAGMA foreign_keys = ON;",
        "",
        "BEGIN TRANSACTION;",
        "",
    ]

    # 1. DDL
    for tname in TABLE_INSERT_ORDER:
        tdef = TABLE_DEFINITIONS[tname]
        lines.append(generate_ddl(tdef))
        lines.append("")

    # 2. INSERTs
    for tname in TABLE_INSERT_ORDER:
        df = load_table(tname, out_dir)
        tdef = TABLE_DEFINITIONS[tname]
        cols = [f.name for f in tdef.fields]
        type_map = {f.name: f.data_type for f in tdef.fields}

        if df.empty:
            continue

        lines.append(f"-- Data for {tname}")
        cols_str = ", ".join(cols)

        # Batch inserts or row-by-row
        for row in df.to_dict(orient="records"):
            vals = [sql_quote(row.get(c), type_map[c]) for c in cols]
            vals_str = ", ".join(vals)
            lines.append(f"INSERT INTO {tname} ({cols_str}) VALUES ({vals_str});")
        lines.append("")

    lines.append("COMMIT;")
    lines.append("")

    with open(sql_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[+] Successfully exported {sql_file}.")
    return sql_file

def verify_sqlite(sql_file: Path):
    print(f"[*] Verifying SQL in SQLite in-memory database...")
    with open(sql_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(sql_content)

    cursor = conn.cursor()
    print("[+] SQLite Verification Results:")
    print("--------------------------------------------------")
    print(f"{'Table Name':<30} | {'Row Count':>10}")
    print("--------------------------------------------------")
    for tname in TABLE_INSERT_ORDER:
        cursor.execute(f"SELECT COUNT(*) FROM {tname};")
        cnt = cursor.fetchone()[0]
        print(f"{tname:<30} | {cnt:>10}")
    print("--------------------------------------------------")
    # Verify FK integrity
    cursor.execute("PRAGMA foreign_key_check;")
    fk_issues = cursor.fetchall()
    if fk_issues:
        print(f"[!] FOREIGN KEY ISSUES DETECTED: {len(fk_issues)}")
        for issue in fk_issues:
            print(f"    {issue}")
        raise RuntimeError("SQLite foreign key check failed!")
    else:
        print("[+] Foreign key integrity check PASSED (0 violations).")

    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Export tables to SQL and optionally verify")
    parser.add_argument("--out", type=str, default="output", help="Output directory")
    parser.add_argument("--verify", action="store_true", help="Load and verify against SQLite in-memory")
    args = parser.parse_args()

    sql_path = generate_seed_sql(out_dir=args.out)
    if args.verify:
        verify_sqlite(sql_path)

if __name__ == "__main__":
    main()
