"""Stage 3: Validation engine for structural integrity, anomaly detection, recall, and quality gates."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from config import get_scale_config
from io_utils import ensure_dir, load_ground_truth, load_table
from schema import TABLE_DEFINITIONS

DT_FMT = "%Y-%m-%d %H:%M:%S"
DATE_FMT = "%Y-%m-%d"

def parse_dt(s: str) -> datetime.datetime:
    return datetime.datetime.strptime(s, DT_FMT)

def parse_date(s: str) -> datetime.date:
    return datetime.datetime.strptime(s, DATE_FMT).date()

class Validator:
    def __init__(self, out_dir: str = "output"):
        self.out_dir = out_dir
        self.tables: Dict[str, pd.DataFrame] = {
            tname: load_table(tname, out_dir) for tname in TABLE_DEFINITIONS.keys()
        }

        # Read scale from source_manifest.json
        manifest_path = Path(out_dir) / "data" / "source_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            self.scale = manifest.get("scale_preset", "starter")
        else:
            self.scale = "starter" if len(self.tables["customers"]) <= 500 else "full"

        self.scale_cfg = get_scale_config(self.scale)
        self.findings: List[Dict[str, Any]] = []
        self.metrics: Dict[str, Any] = {}
        self.gates: Dict[str, bool] = {}

    def add_finding(self, check_name: str, issue_type: str, entity_type: str, entity_id: str, detail: str):
        self.findings.append({
            "check_name": check_name,
            "issue_type": issue_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "detail": detail,
            "is_expected": False,
        })

    def run(self) -> bool:
        print("[*] Running Phase 1: Data-only structural and integrity checks...")
        self.check_leakage()
        self.check_pks_and_regex()
        self.check_foreign_keys()
        self.check_enums_and_nulls()
        self.check_dates_and_lifecycle()
        self.check_arithmetic_and_balances()
        self.check_alerts_and_cases()

        print("[*] Running Phase 2: Ground truth reconciliation and anomaly classification...")
        os.environ["ALLOW_GT"] = "1"
        self.gt_df = load_ground_truth(self.out_dir)
        self.reconcile_anomalies_and_metrics()

        print("[*] Running Phase 3: Acceptance gates evaluation...")
        passed = self.evaluate_acceptance_gates()

        print("[*] Writing validation reports...")
        self.write_reports()
        return passed

    def check_leakage(self):
        forbidden = ["ground_truth", "scenario", "label", "issue_type"]
        for tname, df in self.tables.items():
            for col in df.columns:
                for f in forbidden:
                    if f in col.lower():
                        self.add_finding("LEAKAGE", "DATA_LEAKAGE", "TABLE", tname, f"Column {col} leaks keyword '{f}'")

    def check_pks_and_regex(self):
        for tname, df in self.tables.items():
            tdef = TABLE_DEFINITIONS[tname]
            pks = tdef.primary_key
            if pks:
                dupes = df[df.duplicated(subset=pks, keep=False)]
                for _, r in dupes.iterrows():
                    val = "-".join(str(r[c]) for c in pks)
                    self.add_finding("PK_UNIQUENESS", "DUPLICATE_PK", tname.upper(), val, f"Duplicate PK in {tname}")

            for f in tdef.fields:
                if f.regex:
                    pat = re.compile(f.regex)
                    for val in df[f.name].dropna().astype(str).unique():
                        if val != "" and not pat.match(val):
                            self.add_finding("ID_REGEX_FORMAT", "INVALID_ID_FORMAT", tname.upper(), val, f"Value '{val}' violates {f.regex}")

    def check_foreign_keys(self):
        for tname, df in self.tables.items():
            for fk in TABLE_DEFINITIONS[tname].foreign_keys:
                target_df = self.tables.get(fk.target_table)
                if target_df is None:
                    continue
                valid_keys = set(target_df[fk.target_column].astype(str).unique())
                series = df[fk.column].dropna().astype(str)
                non_blanks = series[series != ""]
                invalid = non_blanks[~non_blanks.isin(valid_keys)]
                for val in invalid.unique():
                    self.add_finding("FK_INTEGRITY", "BROKEN_FK", tname.upper(), str(val), f"FK {fk.column} references missing {fk.target_table}.{fk.target_column}")

    def check_enums_and_nulls(self):
        for tname, df in self.tables.items():
            tdef = TABLE_DEFINITIONS[tname]
            for f in tdef.fields:
                if f.required:
                    nulls = df[df[f.name].isna() | (df[f.name].astype(str).str.strip() == "")]
                    for _, r in nulls.iterrows():
                        pk_val = "-".join(str(r[c]) for c in tdef.primary_key)
                        self.add_finding("REQUIRED_FIELD", "NULL_IN_REQUIRED", tname.upper(), pk_val, f"Required {f.name} is empty in {tname}")
                if f.allowed_values:
                    allowed = set(f.allowed_values)
                    non_blanks = df[df[f.name].astype(str).str.strip() != ""]
                    invalid = non_blanks[~non_blanks[f.name].astype(str).isin(allowed)]
                    for _, r in invalid.iterrows():
                        pk_val = "-".join(str(r[c]) for c in tdef.primary_key)
                        self.add_finding("ENUM_VALIDITY", "INVALID_ENUM_VALUE", tname.upper(), pk_val, f"Field {f.name} value '{r[f.name]}' illegal")

    def check_dates_and_lifecycle(self):
        acc_df = self.tables["accounts"]
        open_dates = {r["account_id"]: parse_date(r["open_date"]) for _, r in acc_df.iterrows()}
        close_dates = {r["account_id"]: parse_date(r["close_date"]) for _, r in acc_df.iterrows() if r["close_date"] != ""}

        # 1. Accounts open_date <= close_date
        for aid, c_dt in close_dates.items():
            if open_dates[aid] > c_dt:
                self.add_finding("DATE_ORDER", "OPEN_AFTER_CLOSE", "ACCOUNT", aid, "open_date is after close_date")
        # 2. First txn >= open_date & txns on closed accounts
        tx_df = self.tables["transactions"]
        for aid, g in tx_df.groupby("account_id"):
            earliest_dt = parse_dt(g["txn_ts"].min()).date()
            if aid in open_dates and earliest_dt < open_dates[aid]:
                self.add_finding("DATE_ORDER", "TXN_BEFORE_OPEN", "ACCOUNT", aid, f"First txn precedes open_date")
            if aid in close_dates:
                for _, r in g.iterrows():
                    if parse_dt(r["txn_ts"]).date() > close_dates[aid]:
                        self.add_finding("DATE_ORDER", "TXN_ON_CLOSED_ACCOUNT", "TRANSACTION", r["txn_id"], f"Txn after close")
        # 3. Status events valid sequence & accounts.status = last status event
        ase_df = self.tables["account_status_events"].sort_values(by=["effective_ts", "event_id"])
        last_status = {}
        for aid, g in ase_df.groupby("account_id"):
            events = g.to_dict("records")
            last_status[aid] = events[-1]["to_status"]
            for i in range(len(events)):
                ev = events[i]
                if i == 0 and ev["reason"] != "OPENED":
                    self.add_finding("LIFECYCLE", "INVALID_INITIAL_EVENT", "ACCOUNT", aid, "First event must be OPENED")
                if i > 0 and ev["from_status"] != events[i - 1]["to_status"]:
                    self.add_finding("LIFECYCLE", "DISCONTINUOUS_STATUS", "ACCOUNT", aid, "Status gap")
        for _, r in acc_df.iterrows():
            aid = r["account_id"]
            if aid in last_status and r["status"] != last_status[aid]:
                self.add_finding("LIFECYCLE", "ACCOUNT_STATUS_MISMATCH", "ACCOUNT", aid, "Status mismatch")
        # 4. Transfer links initiated <= settled
        for _, r in self.tables["transfer_links"].iterrows():
            if parse_dt(r["settled_ts"]) < parse_dt(r["initiated_ts"]):
                self.add_finding("DATE_ORDER", "SETTLED_BEFORE_INITIATED", "TRANSFER", r["transfer_id"], "settled < initiated")
        # 5. Analyst action order and timestamps
        al_map = dict(zip(self.tables["alerts"]["alert_id"], self.tables["alerts"]["created_ts"]))
        for _, r in self.tables["analyst_actions"].iterrows():
            aid = r["alert_id"]
            if aid and aid in al_map and parse_dt(r["action_ts"]) < parse_dt(al_map[aid]):
                self.add_finding("DATE_ORDER", "DISPOSITION_BEFORE_ALERT", "CASE", r["case_id"], "Action precedes alert")

    def check_arithmetic_and_balances(self):
        tx_df = self.tables["transactions"].copy()
        tx_df["dt"] = tx_df["txn_ts"].apply(parse_dt)
        tx_df = tx_df.sort_values(by=["dt", "txn_id"]).reset_index(drop=True)

        acc_df = self.tables["accounts"]
        start_bal = {r["account_id"]: float(r["starting_balance"]) for _, r in acc_df.iterrows()}
        od_limit = {r["account_id"]: float(r["overdraft_limit"]) for _, r in acc_df.iterrows()}

        for aid, g in tx_df.groupby("account_id"):
            last_ba = start_bal.get(aid, 0.0)
            for _, r in g.iterrows():
                bb, ba, amt = float(r["balance_before"]), float(r["balance_after"]), float(r["amount"])
                exp_ba = round(bb + amt, 2) if r["direction"] == "CREDIT" else round(bb - amt, 2)
                if abs(ba - exp_ba) > 0.01:
                    self.add_finding("ARITHMETIC", "BALANCE_MATH_ERROR", "TRANSACTION", r["txn_id"], f"ba {ba} != {exp_ba}")
                if abs(bb - last_ba) > 0.01:
                    self.add_finding("ARITHMETIC", "BALANCE_CHAIN_GAP", "TRANSACTION", r["txn_id"], f"bb {bb} != prev {last_ba}")
                if ba < -od_limit.get(aid, 0.0) - 0.01:
                    self.add_finding("ARITHMETIC", "NEGATIVE_BALANCE_NO_OD", "TRANSACTION", r["txn_id"], f"ba {ba} breached OD limit")
                last_ba = ba

        # Transfer leg amounts
        tx_map = {r["txn_id"]: float(r["amount"]) for _, r in tx_df.iterrows()}
        for _, r in self.tables["transfer_links"].iterrows():
            trf_amt = float(r["amount"])
            if abs(tx_map.get(r["debit_txn_id"], 0.0) - trf_amt) > 0.01 or abs(tx_map.get(r["credit_txn_id"], 0.0) - trf_amt) > 0.01:
                self.add_finding("TRANSFER", "TRANSFER_LEG_MISMATCH", "TRANSFER", r["transfer_id"], "Leg amount mismatch")

        # Alert risk score = clamped sum of components
        comp_df = self.tables["alert_score_components"]
        comp_sums = comp_df.groupby("alert_id")["points"].apply(lambda s: sum(int(x) for x in s)).to_dict()
        for _, r in self.tables["alerts"].iterrows():
            aid = r["alert_id"]
            expected = max(5, min(100, comp_sums.get(aid, 0)))
            if int(r["risk_score"]) != expected:
                self.add_finding("SCORING", "SCORE_MISMATCH", "ALERT", aid, f"Alert score {r['risk_score']} != {expected}")

        # Case score and count recompute
        al_df = self.tables["alerts"]
        case_scores = al_df.groupby("case_id")["risk_score"].apply(lambda s: max(int(x) for x in s)).to_dict()
        case_counts = al_df.groupby("case_id")["alert_id"].count().to_dict()
        for _, r in self.tables["cases"].iterrows():
            cid = r["case_id"]
            if cid in case_scores and int(r["case_score"]) != case_scores[cid]:
                self.add_finding("CASE", "CASE_SCORE_MISMATCH", "CASE", cid, f"case_score {r['case_score']} != max alert {case_scores[cid]}")
            if cid in case_counts and int(r["alert_count"]) != case_counts[cid]:
                self.add_finding("CASE", "CASE_COUNT_MISMATCH", "CASE", cid, f"alert_count {r['alert_count']} != {case_counts[cid]}")

    def check_alerts_and_cases(self):
        al_df = self.tables["alerts"]
        comp_ids = set(self.tables["alert_score_components"]["alert_id"].unique())
        for _, r in al_df.iterrows():
            if not r["trigger_txn_id"] or r["trigger_txn_id"].strip() == "":
                self.add_finding("ALERT", "ALERT_NO_TRIGGER", "ALERT", r["alert_id"], "Headless alert")
            if r["alert_id"] not in comp_ids:
                self.add_finding("ALERT", "MISSING_COMPONENTS", "ALERT", r["alert_id"], "Alert has zero score components")

        ranks = al_df["priority_rank"].astype(int).tolist()
        if sorted(ranks) != list(range(1, len(ranks) + 1)):
            self.add_finding("PRIORITY_RANKING", "NON_CONTIGUOUS_RANK", "ALERTS", "GLOBAL", "priority_rank is not 1..N")

    def reconcile_anomalies_and_metrics(self):
        inj_gt = self.gt_df[self.gt_df["label"] == "DATA_QUALITY_ISSUE"]
        expected_anomalies: Dict[str, Set[str]] = {}
        for _, r in inj_gt.iterrows():
            expected_anomalies.setdefault(r["issue_type"], set()).add(str(r["entity_id"]))

        unexpected_count = 0
        found_expected: Dict[str, int] = {k: 0 for k in expected_anomalies.keys()}
        for f in self.findings:
            itype, eid = f["issue_type"], f["entity_id"]
            if itype in expected_anomalies and eid in expected_anomalies[itype]:
                f["is_expected"] = True
                found_expected[itype] += 1
            else:
                f["is_expected"] = False
                unexpected_count += 1

        self.metrics["unexpected_failures"] = unexpected_count
        self.metrics["injected_anomalies_planted"] = {k: len(v) for k, v in expected_anomalies.items()}
        self.metrics["injected_anomalies_found"] = found_expected

        # Recall per scenario type
        true_scns = self.gt_df[self.gt_df["label"] == "SUSPICIOUS"]
        al_df = self.tables["alerts"]
        alerts_by_trigger = {}
        for _, r in al_df.iterrows():
            alerts_by_trigger.setdefault(r["trigger_txn_id"], []).append(r["rule_id"])

        recall_table = {}
        for stype, g in true_scns.groupby("scenario_type"):
            total_scn = len(g)
            detected = 0
            for _, r in g.iterrows():
                trig, exp_r = r["trigger_txn_id"], r["expected_rule_id"]
                if trig in alerts_by_trigger and exp_r in alerts_by_trigger[trig]:
                    detected += 1
            recall_table[stype] = {"planted": total_scn, "detected": detected, "recall": round(detected / total_scn, 4) if total_scn else 0.0}

        self.metrics["detection_recall"] = recall_table

        # FP metrics
        fp_scns = self.gt_df[self.gt_df["label"] == "BENIGN_LOOKALIKE"]
        fp_triggers = set(fp_scns["trigger_txn_id"].unique())
        fp_alerts = [a for _, a in al_df.iterrows() if a["trigger_txn_id"] in fp_triggers]
        self.metrics["fp_alerts_count"] = len(fp_alerts)
        fp_closed = sum(1 for a in fp_alerts if a["status"] == "CLOSED_FALSE_POSITIVE")
        self.metrics["fp_closed_false_positive_pct"] = round(fp_closed / len(fp_alerts), 4) if fp_alerts else 0.0

        # Precision@K & baseline alerts
        inj_cases = set(self.gt_df[self.gt_df["issue_type"] == "DISPOSITION_BEFORE_ALERT"]["entity_id"])
        inj_alerts = set(self.gt_df[self.gt_df["issue_type"] == "ALERT_NO_TRIGGER"]["entity_id"]) | set(al_df[al_df["case_id"].isin(inj_cases)]["alert_id"])
        baseline_alerts = al_df[~al_df["alert_id"].isin(inj_alerts) & (al_df["trigger_txn_id"] != "")].copy()
        baseline_alerts["_pr"] = baseline_alerts["priority_rank"].astype(int)
        baseline_alerts = baseline_alerts.sort_values(by="_pr").reset_index(drop=True)
        self.metrics["baseline_alerts_count"] = len(baseline_alerts)

        true_triggers = set(true_scns["trigger_txn_id"].unique())
        p_at_k = {}
        for k in [50, 100, 250]:
            k_eff = min(k, len(baseline_alerts))
            if k_eff > 0:
                top_k = baseline_alerts.iloc[:k_eff]
                tp = sum(1 for _, a in top_k.iterrows() if a["trigger_txn_id"] in true_triggers)
                p_at_k[f"P@{k}"] = round(tp / k_eff, 4)
        self.metrics["precision_at_k"] = p_at_k

        # Disposition agreement
        all_scns = self.gt_df[self.gt_df["expected_decision"].isin(["TRUE_POSITIVE", "FALSE_POSITIVE"])]
        agreed, total = 0, 0
        for _, r in all_scns.iterrows():
            trig, exp_dec = r["trigger_txn_id"], r["expected_decision"]
            if trig in alerts_by_trigger:
                matched_al = al_df[al_df["trigger_txn_id"] == trig]
                for _, a in matched_al.iterrows():
                    total += 1
                    act_dec = "TRUE_POSITIVE" if a["status"] == "CLOSED_TRUE_POSITIVE" else ("FALSE_POSITIVE" if a["status"] == "CLOSED_FALSE_POSITIVE" else "OPEN")
                    if act_dec == exp_dec:
                        agreed += 1
        self.metrics["disposition_agreement"] = round(agreed / total, 4) if total else 0.0

        # Unmapped alerts
        all_gt_triggers = set(self.gt_df["trigger_txn_id"].dropna().unique())
        unmapped = sum(1 for _, a in baseline_alerts.iterrows() if a["trigger_txn_id"] not in all_gt_triggers)
        self.metrics["unmapped_alerts_count"] = unmapped

    def evaluate_acceptance_gates(self) -> bool:
        g1 = self.metrics["unexpected_failures"] == 0
        g2 = all(self.metrics["injected_anomalies_found"].get(k, 0) == v for k, v in self.metrics["injected_anomalies_planted"].items())
        g3 = all(v["recall"] >= 0.95 for v in self.metrics["detection_recall"].values())
        target = self.scale_cfg["alerts_target"]
        base_cnt = self.metrics["baseline_alerts_count"]
        g4_vol = (0.90 * target <= base_cnt <= 1.10 * target) if self.scale == "full" else True
        g4_fp = (self.metrics["fp_alerts_count"] >= 0.20 * base_cnt) if base_cnt else False
        g5 = not any(f["check_name"] == "LEAKAGE" for f in self.findings)
        self.gates = {
            "Gate 1: Zero Unexpected Structural Failures": g1,
            "Gate 2: Injected Anomalies Found Exactly as Planted": g2,
            "Gate 3: Detection Recall >= 0.95 for All TRUE Types": g3,
            "Gate 4: Alert Target & FP Representation (>=20%)": g4_vol and g4_fp,
            "Gate 5: Zero Ground Truth Leakage": g5,
        }
        print("\n================ ACCEPTANCE GATES ================")
        all_passed = True
        for g_name, status in self.gates.items():
            print(f"[{'PASS' if status else 'FAIL'}] {g_name}")
            if not status: all_passed = False
        print("==================================================\n")
        return all_passed

    def write_reports(self):
        rep_dir = ensure_dir(Path(self.out_dir) / "reports")

        # 1. alert_ranking.csv
        al_df = self.tables["alerts"].sort_values(by="priority_rank")
        cols = ["priority_rank", "alert_id", "rule_id", "risk_score", "severity", "case_id", "explanation"]
        al_df[cols].to_csv(rep_dir / "alert_ranking.csv", index=False, lineterminator="\n")

        # 2. validation_results.json
        results = {
            "scale": self.scale,
            "gates": self.gates,
            "metrics": self.metrics,
            "unexpected_failures": self.metrics["unexpected_failures"],
        }
        with open(rep_dir / "validation_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, sort_keys=True)

        # 3. validation_summary.md
        md = [
            "# Pipeline Validation Summary Report",
            f"**Scale Preset:** `{self.scale}` | **Audit Status:** `{'PASS' if all(self.gates.values()) else 'FAIL'}`",
            "",
            "## 1. Acceptance Gates",
            "",
            "| Gate | Status | Condition |",
            "|---|---|---|",
        ]
        for g_name, st in self.gates.items():
            md.append(f"| **{g_name}** | `{'PASS' if st else 'FAIL'}` | Verified against schema & ground truth |")
        md.extend([
            "",
            "## 2. Detection Recall by Planted Scenario",
            "",
            "| Scenario Type | Planted Scenarios | Detected Alerts | Recall Rate | Status |",
            "|---|---|---|---|---|",
        ])
        for stype, rec in sorted(self.metrics["detection_recall"].items()):
            md.append(f"| `{stype}` | {rec['planted']} | {rec['detected']} | {rec['recall']:.1%} | `{'PASS' if rec['recall'] >= 0.95 else 'FAIL'}` |")

        md.extend([
            "",
            "## 3. Labelled Injected Data Quality Anomalies",
            "",
            "| Anomaly Issue Type | Planted Count | Detected Independently | Status |",
            "|---|---|---|---|",
        ])
        for itype, planted in sorted(self.metrics["injected_anomalies_planted"].items()):
            found = self.metrics["injected_anomalies_found"].get(itype, 0)
            md.append(f"| `{itype}` | {planted} | {found} | `{'MATCH' if found == planted else 'MISMATCH'}` |")

        md.extend([
            "",
            "## 4. Key Prioritization & Performance Metrics",
            "",
            f"- **Baseline Alerts (excluding injected):** {self.metrics['baseline_alerts_count']}",
            f"- **False-Positive Mapped Alerts:** {self.metrics['fp_alerts_count']} ({self.metrics['fp_alerts_count'] / max(1, self.metrics['baseline_alerts_count']):.1%})",
            f"- **FP Closed as False Positive:** {self.metrics['fp_closed_false_positive_pct']:.1%}",
            f"- **Disposition Agreement with Ground Truth:** {self.metrics['disposition_agreement']:.1%}",
            f"- **Unmapped Alerts:** {self.metrics['unmapped_alerts_count']}",
            f"- **Precision@50:** {self.metrics['precision_at_k'].get('P@50', 0.0):.1%}",
            f"- **Precision@100:** {self.metrics['precision_at_k'].get('P@100', 0.0):.1%}",
            f"- **Precision@250:** {self.metrics['precision_at_k'].get('P@250', 0.0):.1%}",
            "",
            "### Alert Distribution by Primary Rule",
            "",
            "| Rule ID | Alert Count |",
            "|---|---|",
        ])
        for rid, cnt in al_df["rule_id"].value_counts().items():
            md.append(f"| `{rid}` | {cnt} |")

        md.extend([
            "",
            "### Alert Distribution by Severity",
            "",
            "| Severity Band | Alert Count |",
            "|---|---|",
        ])
        for sev, cnt in al_df["severity"].value_counts().items():
            md.append(f"| `{sev}` | {cnt} |")
        md.append("")

        with open(rep_dir / "validation_summary.md", "w", encoding="utf-8") as f:
            f.write("\n".join(md))

def main():
    parser = argparse.ArgumentParser(description="Stage 3: Validation and Quality Checks")
    parser.add_argument("--out", type=str, default="output", help="Output directory")
    args = parser.parse_args()
    if not Validator(out_dir=args.out).run():
        sys.exit(1)

if __name__ == "__main__":
    main()
