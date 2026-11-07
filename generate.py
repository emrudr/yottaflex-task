"""Stage 1 Orchestrator: Generate synthetic banking universe with deterministic seeds."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from config import SEED, get_scale_config
from gen_master import generate_master_data
from gen_scenarios import ScenarioBuilder
from gen_transactions import generate_transactions_dataset
from io_utils import compute_sha256, ensure_dir, save_ground_truth, save_table
from schema import DEFAULT_RULES_SEED_DATA, generate_data_dictionary_md, generate_rules_md

def update_account_latest_status(accounts: List[Dict[str, Any]], status_events: List[Dict[str, Any]]):
    """Ensure accounts.status matches the latest chronological status event."""
    latest_status: Dict[str, str] = {}
    sorted_events = sorted(status_events, key=lambda x: (x["effective_ts"], x["event_id"]))
    for ev in sorted_events:
        latest_status[ev["account_id"]] = ev["to_status"]

    for acc in accounts:
        aid = acc["account_id"]
        if aid in latest_status:
            acc["status"] = latest_status[aid]

def save_source_manifest(out_dir: str, cfg: Dict[str, Any], seed: int):
    """Save metadata and cryptographic checksums manifest for data integrity."""
    data_dir = ensure_dir(Path(out_dir) / "data")
    manifest = {
        "generator_version": "2.0.0",
        "scale_preset": "starter" if cfg["customers"] <= 500 else "full",
        "seed": seed,
        "generated_at": "2026-11-01 00:00:00",
        "entity_counts": {
            "customers": cfg["customers"],
            "accounts": cfg["accounts"],
            "transactions": cfg["transactions"],
            "merchants": cfg["merchants"],
            "analysts": cfg["analysts"],
        },
        "file_checksums": {},
    }
    for csv_file in sorted(data_dir.glob("*.csv")):
        manifest["file_checksums"][csv_file.name] = compute_sha256(csv_file)

    with open(data_dir / "source_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

def main():
    parser = argparse.ArgumentParser(description="Stage 1: Generate Synthetic Banking Universe")
    parser.add_argument("--seed", type=int, default=SEED, help="Random seed")
    parser.add_argument("--scale", type=str, default="starter", choices=["starter", "full"], help="Scale preset")
    parser.add_argument("--out", type=str, default="output", help="Output directory")
    args = parser.parse_args()

    cfg = get_scale_config(args.scale)
    print(f"[*] Starting synthetic data generation (Scale: {args.scale}, Seed: {args.seed})...")

    # 1. Master entities
    master = generate_master_data(cfg, args.seed)

    # 2. Planted scenarios & anomalies
    scenarios = ScenarioBuilder(master, cfg, args.seed).build_all()

    # 3. Background transactions & balance sweep
    transactions, transfer_links, account_devices = generate_transactions_dataset(
        master, scenarios, cfg["transactions"], args.seed
    )

    # 4. Sync account status
    update_account_latest_status(master["accounts"], master["account_status_events"])

    # 5. Save tables
    save_table(master["customers"], "customers", args.out)
    save_table(master["accounts"], "accounts", args.out)
    save_table(master["account_status_events"], "account_status_events", args.out)
    save_table(master["merchants"], "merchants", args.out)
    save_table(master["devices"], "devices", args.out)
    save_table(account_devices, "account_devices", args.out)
    save_table(master["analysts"], "analysts", args.out)
    save_table(DEFAULT_RULES_SEED_DATA, "risk_rules", args.out)
    save_table(transfer_links, "transfer_links", args.out)
    save_table(transactions, "transactions", args.out)

    # 6. Save isolated ground truth
    save_ground_truth(scenarios["ground_truth"], args.out)

    # 7. Documentation & manifest
    docs_dir = ensure_dir(Path("docs"))
    with open(docs_dir / "data_dictionary.md", "w", encoding="utf-8") as f:
        f.write(generate_data_dictionary_md())
    with open(docs_dir / "rules.md", "w", encoding="utf-8") as f:
        f.write(generate_rules_md(DEFAULT_RULES_SEED_DATA))

    save_source_manifest(args.out, cfg, args.seed)
    print(f"[+] Generation complete: {len(transactions)} txns, {len(master['accounts'])} accounts, {len(master['customers'])} customers.")

if __name__ == "__main__":
    main()
