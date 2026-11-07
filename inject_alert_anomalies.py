"""Stage 2b: Inject alert and case-level labelled data quality anomalies."""

from __future__ import annotations

import argparse
import datetime
import os
import random
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from config import (
    DATA_START,
    SEED,
    format_action_id,
    format_alert_id,
    format_case_id,
    get_scale_config,
)
from io_utils import load_ground_truth, load_table, save_ground_truth, save_table

DT_FMT = "%Y-%m-%d %H:%M:%S"

def parse_dt(s: str) -> datetime.datetime:
    return datetime.datetime.strptime(s, DT_FMT)

def format_dt(dt: datetime.datetime) -> str:
    return dt.strftime(DT_FMT)

def run_injections(seed: int = SEED, out_dir: str = "output"):
    # Allow loading ground truth
    os.environ["ALLOW_GT"] = "1"

    print(f"[*] Starting alert anomaly injection (Seed: {seed})...")
    rng = random.Random(f"{seed}:inject_alert_anomalies")

    alerts_df = load_table("alerts", out_dir)
    evidence_df = load_table("alert_evidence", out_dir)
    components_df = load_table("alert_score_components", out_dir)
    cases_df = load_table("cases", out_dir)
    actions_df = load_table("analyst_actions", out_dir)
    accounts_df = load_table("accounts", out_dir)
    customers_df = load_table("customers", out_dir)
    txns_df = load_table("transactions", out_dir)
    gt_df = load_ground_truth(out_dir)

    scale_cfg = get_scale_config("starter" if len(customers_df) <= 500 else "full")
    counts = scale_cfg["scenario_counts"]

    n_no_trigger = counts["INJ_ALERT_NO_TRIGGER"]
    n_disp_before = counts["INJ_DISPOSITION_BEFORE_ALERT"]

    # Convert to lists of dicts
    alerts = alerts_df.to_dict(orient="records")
    evidence = evidence_df.to_dict(orient="records")
    components = components_df.to_dict(orient="records")
    cases = cases_df.to_dict(orient="records")
    actions = actions_df.to_dict(orient="records")
    gt_records = gt_df.to_dict(orient="records")

    # Get max IDs
    def max_int_id(items: List[Dict[str, Any]], key: str, prefix_len: int) -> int:
        max_val = 0
        for item in items:
            val_str = str(item.get(key, ""))
            if "-" in val_str:
                parts = val_str.split("-")
                try:
                    num = int(parts[-1])
                    if num > max_val:
                        max_val = num
                except ValueError:
                    pass
        return max_val

    alert_idx = max_int_id(alerts, "alert_id", 0)
    case_idx = max_int_id(cases, "case_id", 0)
    action_idx = max_int_id(actions, "action_id", 0)
    gt_idx = max_int_id(gt_records, "gt_id", 0)
    scn_idx = max_int_id(gt_records, "scenario_id", 0)

    # Pick candidate accounts not already flagged in ground truth
    used_accs = {g["account_id"] for g in gt_records if g["account_id"]}
    cand_accs = [
        a for a in accounts_df.to_dict(orient="records")
        if a["account_id"] not in used_accs and a["status"] == "ACTIVE"
    ]
    rng.shuffle(cand_accs)

    # 1. ALERT_NO_TRIGGER_TXN
    for i in range(min(n_no_trigger, len(cand_accs))):
        acc = cand_accs[i]
        aid = acc["account_id"]
        cid = acc["customer_id"]

        alert_idx += 1
        alt_id = format_alert_id(alert_idx)

        case_idx += 1
        cid_case = format_case_id(case_idx)

        c_dt = parse_dt("2026-07-10 10:00:00") + datetime.timedelta(days=i * 5)
        c_ts = format_dt(c_dt)

        # Alert row
        alerts.append({
            "alert_id": alt_id,
            "rule_id": "R01",
            "trigger_txn_id": "",
            "account_id": aid,
            "customer_id": cid,
            "created_ts": c_ts,
            "risk_score": 60,
            "severity": "MEDIUM",
            "priority_rank": len(alerts) + 1,
            "status": "OPEN",
            "case_id": cid_case,
            "explanation": "VELOCITY_SPIKE: synthetic headless anomaly; score 60 (BASE_R01:+60)",
        })

        # Component
        components.append({
            "alert_id": alt_id,
            "seq": 1,
            "component_code": "BASE_R01",
            "rule_id": "R01",
            "points": 60,
            "detail": "Base points for R01 (injected headless anomaly)",
        })

        # Case row
        cases.append({
            "case_id": cid_case,
            "primary_account_id": aid,
            "opened_ts": c_ts,
            "closed_ts": None,
            "alert_count": 1,
            "case_score": 60,
            "priority": "P3",
            "status": "UNDER_REVIEW",
            "assigned_analyst_id": "ANL-001",
            "final_disposition": None,
        })

        # Actions
        action_idx += 1
        actions.append({
            "action_id": format_action_id(action_idx),
            "case_id": cid_case,
            "alert_id": None,
            "analyst_id": "ANL-001",
            "action_type": "ASSIGN",
            "disposition": None,
            "action_ts": format_dt(c_dt + datetime.timedelta(minutes=10)),
            "note": "Case assigned to ANL-001",
        })

        action_idx += 1
        actions.append({
            "action_id": format_action_id(action_idx),
            "case_id": cid_case,
            "alert_id": None,
            "analyst_id": "ANL-001",
            "action_type": "REVIEW_START",
            "disposition": None,
            "action_ts": format_dt(c_dt + datetime.timedelta(minutes=30)),
            "note": "Review started by ANL-001",
        })

        # Ground truth
        gt_idx += 1
        scn_idx += 1
        gt_records.append({
            "gt_id": f"GT-{gt_idx:06d}",
            "scenario_id": f"SCN-{scn_idx:06d}",
            "scenario_type": "INJ_ALERT_NO_TRIGGER",
            "label": "DATA_QUALITY_ISSUE",
            "issue_type": "ALERT_NO_TRIGGER",
            "entity_type": "ALERT",
            "entity_id": alt_id,
            "account_id": aid,
            "trigger_txn_id": "",
            "expected_rule_id": "R01",
            "expected_alert": "Y",
            "expected_decision": "N/A",
            "notes": "Alert injected without trigger transaction or evidence",
        })

    # 2. DISPOSITION_BEFORE_ALERT
    # Find real debit transactions from cand_accs
    cand_txns = txns_df[
        (txns_df["account_id"].isin({a["account_id"] for a in cand_accs[n_no_trigger:]}))
        & (txns_df["direction"] == "DEBIT")
    ].to_dict(orient="records")
    rng.shuffle(cand_txns)

    for i in range(min(n_disp_before, len(cand_txns))):
        tx = cand_txns[i]
        aid = tx["account_id"]
        cid = accounts_df.loc[accounts_df["account_id"] == aid, "customer_id"].iloc[0]
        tx_dt = parse_dt(tx["txn_ts"])
        alt_dt = tx_dt + datetime.timedelta(minutes=5)
        alt_ts = format_dt(alt_dt)

        alert_idx += 1
        alt_id = format_alert_id(alert_idx)

        case_idx += 1
        cid_case = format_case_id(case_idx)

        # Disposition timestamp 2 days BEFORE alert creation!
        disp_dt = alt_dt - datetime.timedelta(days=2)
        disp_ts = format_dt(disp_dt)

        alerts.append({
            "alert_id": alt_id,
            "rule_id": "R01",
            "trigger_txn_id": tx["txn_id"],
            "account_id": aid,
            "customer_id": cid,
            "created_ts": alt_ts,
            "risk_score": 75,
            "severity": "HIGH",
            "priority_rank": len(alerts) + 1,
            "status": "CLOSED_TRUE_POSITIVE",
            "case_id": cid_case,
            "explanation": f"VELOCITY_SPIKE: synthetic timing anomaly; score 75 (BASE_R01:+60, BONUS_COUNT_GE_10:+15)",
        })

        evidence.append({
            "alert_id": alt_id,
            "txn_id": tx["txn_id"],
            "role": "TRIGGER",
        })

        components.append({
            "alert_id": alt_id,
            "seq": 1,
            "component_code": "BASE_R01",
            "rule_id": "R01",
            "points": 60,
            "detail": "Base points for R01",
        })
        components.append({
            "alert_id": alt_id,
            "seq": 2,
            "component_code": "BONUS_COUNT_GE_10",
            "rule_id": "R01",
            "points": 15,
            "detail": "Burst bonus",
        })

        close_ts = format_dt(disp_dt + datetime.timedelta(minutes=10))
        cases.append({
            "case_id": cid_case,
            "primary_account_id": aid,
            "opened_ts": alt_ts,
            "closed_ts": close_ts,
            "alert_count": 1,
            "case_score": 75,
            "priority": "P2",
            "status": "CLOSED",
            "assigned_analyst_id": "ANL-002",
            "final_disposition": "TRUE_POSITIVE",
        })

        # Actions before alert
        action_idx += 1
        actions.append({
            "action_id": format_action_id(action_idx),
            "case_id": cid_case,
            "alert_id": None,
            "analyst_id": "ANL-002",
            "action_type": "ASSIGN",
            "disposition": None,
            "action_ts": format_dt(disp_dt - datetime.timedelta(hours=2)),
            "note": "Case assigned prematurely",
        })

        action_idx += 1
        actions.append({
            "action_id": format_action_id(action_idx),
            "case_id": cid_case,
            "alert_id": None,
            "analyst_id": "ANL-002",
            "action_type": "REVIEW_START",
            "disposition": None,
            "action_ts": format_dt(disp_dt - datetime.timedelta(hours=1)),
            "note": "Premature review started",
        })

        action_idx += 1
        actions.append({
            "action_id": format_action_id(action_idx),
            "case_id": cid_case,
            "alert_id": alt_id,
            "analyst_id": "ANL-002",
            "action_type": "DISPOSITION",
            "disposition": "TRUE_POSITIVE",
            "action_ts": disp_ts,
            "note": "Premature disposition before alert timestamp",
        })

        action_idx += 1
        actions.append({
            "action_id": format_action_id(action_idx),
            "case_id": cid_case,
            "alert_id": None,
            "analyst_id": "ANL-002",
            "action_type": "CLOSE",
            "disposition": None,
            "action_ts": close_ts,
            "note": "Case closed prematurely",
        })

        # Ground truth
        gt_idx += 1
        scn_idx += 1
        gt_records.append({
            "gt_id": f"GT-{gt_idx:06d}",
            "scenario_id": f"SCN-{scn_idx:06d}",
            "scenario_type": "INJ_DISPOSITION_BEFORE_ALERT",
            "label": "DATA_QUALITY_ISSUE",
            "issue_type": "DISPOSITION_BEFORE_ALERT",
            "entity_type": "CASE",
            "entity_id": cid_case,
            "account_id": aid,
            "trigger_txn_id": tx["txn_id"],
            "expected_rule_id": "R01",
            "expected_alert": "Y",
            "expected_decision": "N/A",
            "notes": "Analyst disposition timestamp precedes alert creation timestamp",
        })

    # Save updated tables
    print(f"[+] Appended {n_no_trigger} headless alerts and {n_disp_before} inverted disposition cases.")
    save_table(pd.DataFrame(alerts), "alerts", out_dir)
    save_table(pd.DataFrame(evidence), "alert_evidence", out_dir)
    save_table(pd.DataFrame(components), "alert_score_components", out_dir)
    save_table(pd.DataFrame(cases), "cases", out_dir)
    save_table(pd.DataFrame(actions), "analyst_actions", out_dir)
    save_ground_truth(pd.DataFrame(gt_records), out_dir)

def main():
    parser = argparse.ArgumentParser(description="Stage 2b: Inject Alert-level Anomalies")
    parser.add_argument("--seed", type=int, default=SEED, help="Random seed")
    parser.add_argument("--out", type=str, default="output", help="Output directory")
    args = parser.parse_args()

    run_injections(seed=args.seed, out_dir=args.out)

if __name__ == "__main__":
    main()

