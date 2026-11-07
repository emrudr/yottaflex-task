"""Stage 2: Deterministic risk detection engine, explainable scoring, case grouping, and analyst triage."""

from __future__ import annotations

import argparse
import datetime
import json
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from config import (
    DATE_FMT,
    format_action_id,
    format_alert_id,
    format_case_id,
)
from io_utils import load_table, save_table

DT_FMT = "%Y-%m-%d %H:%M:%S"

def parse_dt(s: str) -> datetime.datetime:
    return datetime.datetime.strptime(s, DT_FMT)

def format_dt(dt: datetime.datetime) -> str:
    return dt.strftime(DT_FMT)

class RulesEngine:
    def __init__(self, out_dir: str = "output"):
        self.out_dir = out_dir
        self.tx_df = load_table("transactions", out_dir)
        self.tx_df["dt"] = self.tx_df["txn_ts"].apply(parse_dt)
        self.tx_df["amt_f"] = self.tx_df["amount"].astype(float)
        self.tx_df = self.tx_df.sort_values(by=["dt", "txn_id"]).reset_index(drop=True)

        self.acc_df = load_table("accounts", out_dir).set_index("account_id")
        self.cust_df = load_table("customers", out_dir).set_index("customer_id")
        self.merch_df = load_table("merchants", out_dir).set_index("merchant_id")
        self.dev_df = load_table("devices", out_dir).set_index("device_id")
        self.trf_df = load_table("transfer_links", out_dir)

        # Device account sharing counts across dataset
        self.dev_sharing = self.tx_df.groupby("device_id")["account_id"].nunique().to_dict()

        # Load rules parameters
        rules_table = load_table("risk_rules", out_dir)
        self.rules: Dict[str, Dict[str, Any]] = {}
        for _, r in rules_table.iterrows():
            rid = r["rule_id"]
            self.rules[rid] = {
                "rule_name": r["rule_name"],
                "base_points": int(r["base_points"]),
                "params": json.loads(r["parameters_json"]) if isinstance(r["parameters_json"], str) else r["parameters_json"],
            }

    def is_trusted_customer(self, cid: str) -> bool:
        """Customer has verified KYC, low risk tier, and tenure >= 3 years."""
        if cid not in self.cust_df.index:
            return False
        c = self.cust_df.loc[cid]
        onboard = datetime.datetime.strptime(c["onboarding_date"], DATE_FMT).date()
        p = self.rules["A02"]["params"]
        return (
            onboard <= datetime.date(2023, 10, 31)
            and c["kyc_status"] == p["required_kyc_status"]
            and c["kyc_risk_tier"] == p["required_kyc_tier"]
        )

    def eval_r01(self) -> List[Dict[str, Any]]:
        """R01: High volume of debit transactions within a 60-minute window."""
        matches = []
        r = self.rules["R01"]
        p = r["params"]
        w_sec = p["window_minutes"] * 60

        for aid, g in self.tx_df[self.tx_df["direction"] == "DEBIT"].groupby("account_id"):
            tx_list = g.to_dict("records")
            n = len(tx_list)
            i = 0
            while i < n:
                j = i
                while j < n and (tx_list[j]["dt"] - tx_list[i]["dt"]).total_seconds() <= w_sec:
                    j += 1
                cnt = j - i
                if cnt >= p["min_count"]:
                    burst = tx_list[i:j]
                    tot = sum(t["amt_f"] for t in burst)
                    comps = [{"code": "BASE_POINTS", "points": r["base_points"], "detail": f"{cnt} debits in 60m"}]
                    if cnt >= p["bonus_count_threshold"]:
                        comps.append({"code": "BONUS_HIGH_COUNT", "points": p["bonus_count_points"], "detail": f"Debits >= {p['bonus_count_threshold']}"})
                    if tot >= p["bonus_amount_threshold"]:
                        comps.append({"code": "BONUS_HIGH_VOLUME", "points": p["bonus_amount_points"], "detail": f"Burst volume {tot:.2f} >= {p['bonus_amount_threshold']}"})
                    matches.append({
                        "rule_id": "R01",
                        "trigger_txn": burst[-1],
                        "evidence": burst,
                        "components": comps,
                    })
                    i = j
                else:
                    i += 1
        return matches

    def eval_r02(self) -> List[Dict[str, Any]]:
        """R02: Significant debit activity on a newly observed device for an established account."""
        matches = []
        r = self.rules["R02"]
        p = r["params"]

        for aid, g in self.tx_df.groupby("account_id"):
            seen_devs: Set[str] = set()
            prior_txns = 0
            for tx in g.to_dict("records"):
                did = tx["device_id"]
                if did and did not in seen_devs:
                    seen_devs.add(did)
                    if tx["direction"] == "DEBIT" and tx["amt_f"] >= p["min_amount"] and prior_txns >= p["min_prior_account_txns"]:
                        comps = [{"code": "BASE_POINTS", "points": r["base_points"], "detail": f"New device {did} debit {tx['amt_f']}"}]
                        if tx["amt_f"] >= p["bonus_large_amount"]:
                            comps.append({"code": "BONUS_LARGE_AMOUNT", "points": p["bonus_large_points"], "detail": f"Amount >= {p['bonus_large_amount']}"})
                        is_emu = str(self.dev_df.loc[did, "is_emulator"]).lower() in ("true", "1") if did in self.dev_df.index else False
                        is_shared = self.dev_sharing.get(did, 1) >= p["bonus_emulator_or_shared_accounts"]
                        if is_emu or is_shared:
                            comps.append({"code": "BONUS_EMULATOR_SHARED", "points": p["bonus_emulator_points"], "detail": "Emulator or shared hardware"})
                        matches.append({
                            "rule_id": "R02",
                            "trigger_txn": tx,
                            "evidence": [tx],
                            "components": comps,
                        })
                prior_txns += 1
        return matches

    def eval_r03(self) -> List[Dict[str, Any]]:
        """R03: Circular transfer path returning funds to origin within 72 hours."""
        matches = []
        r = self.rules["R03"]
        p = r["params"]
        w_sec = p["max_window_hours"] * 3600

        # Build adjacency graph
        links = self.trf_df.copy()
        links["init_dt"] = links["initiated_ts"].apply(parse_dt)
        links["amt_f"] = links["amount"].astype(float)
        tx_dict = {r["txn_id"]: r for r in self.tx_df.to_dict("records")}

        # Trace 2 to 5 hop cycles
        for _, l1 in links[links["amt_f"] >= p["min_transfer_amount"]].iterrows():
            a0, a1 = l1["source_account_id"], l1["dest_account_id"]
            t0 = l1["init_dt"]
            c1_candidates = links[
                (links["source_account_id"] == a1)
                & (links["amt_f"] >= p["min_transfer_amount"])
                & (links["init_dt"] >= t0)
                & (links["init_dt"] <= t0 + datetime.timedelta(seconds=w_sec))
            ]
            for _, l2 in c1_candidates.iterrows():
                a2 = l2["dest_account_id"]
                # 2-hop cycle: a0 -> a1 -> a0
                if a2 == a0:
                    self._record_r03_match(matches, [l1, l2], tx_dict)
                    continue
                # 3-hop cycle: a0 -> a1 -> a2 -> a0
                c2_candidates = links[
                    (links["source_account_id"] == a2)
                    & (links["dest_account_id"] == a0)
                    & (links["amt_f"] >= p["min_transfer_amount"])
                    & (links["init_dt"] >= l2["init_dt"])
                    & (links["init_dt"] <= t0 + datetime.timedelta(seconds=w_sec))
                ]
                for _, l3 in c2_candidates.iterrows():
                    self._record_r03_match(matches, [l1, l2, l3], tx_dict)
        return matches

    def _record_r03_match(self, matches: List[Dict[str, Any]], cycle_links: List[Any], tx_dict: Dict[str, Any]):
        r = self.rules["R03"]
        p = r["params"]
        closing_link = cycle_links[-1]
        closing_tx = tx_dict.get(closing_link["debit_txn_id"])
        if not closing_tx:
            return

        evidence = [tx_dict[l["debit_txn_id"]] for l in cycle_links if l["debit_txn_id"] in tx_dict]
        accounts = [l["source_account_id"] for l in cycle_links]
        customers = {self.acc_df.loc[aid, "customer_id"] for aid in accounts if aid in self.acc_df.index}

        comps = [{"code": "BASE_POINTS", "points": r["base_points"], "detail": f"Circular loop across {len(accounts)} accounts"}]
        if len(customers) >= p["bonus_distinct_customers"]:
            comps.append({"code": "BONUS_DISTINCT_CUSTOMERS", "points": p["bonus_distinct_customers_points"], "detail": f">= {p['bonus_distinct_customers']} distinct customers"})
        retention = float(closing_link["amount"]) / float(cycle_links[0]["amount"])
        if retention >= p["bonus_retention_ratio"]:
            comps.append({"code": "BONUS_CAPITAL_RETENTION", "points": p["bonus_retention_points"], "detail": f"Retention {retention:.1%} >= {p['bonus_retention_ratio']:.0%}"})

        # Adjustment A01 if same owner
        if len(customers) == 1:
            comps.append({"code": "ADJ_SAME_OWNER", "points": self.rules["A01"]["base_points"], "detail": "All accounts in cycle owned by same customer"})

        matches.append({
            "rule_id": "R03",
            "trigger_txn": closing_tx,
            "evidence": evidence,
            "components": comps,
        })

    def eval_r04(self) -> List[Dict[str, Any]]:
        """R04: Substantial transaction following an inactivity gap exceeding 180 days."""
        matches = []
        r = self.rules["R04"]
        p = r["params"]
        gap_days = p["inactivity_gap_days"]

        for aid, g in self.tx_df.groupby("account_id"):
            tx_list = g.to_dict("records")
            seen_devs: Set[str] = set()
            for i in range(1, len(tx_list)):
                prev_tx = tx_list[i - 1]
                curr_tx = tx_list[i]
                gap = (curr_tx["dt"] - prev_tx["dt"]).days
                if gap >= gap_days and curr_tx["amt_f"] >= p["min_amount"]:
                    comps = [{"code": "BASE_POINTS", "points": r["base_points"], "detail": f"Activity after {gap} days dormancy"}]
                    bb = float(curr_tx["balance_before"])
                    if curr_tx["direction"] == "DEBIT" and bb > 0:
                        drain_ratio = curr_tx["amt_f"] / bb
                        if drain_ratio >= p["bonus_debit_drain_ratio"]:
                            comps.append({"code": "BONUS_DEBIT_DRAIN", "points": p["bonus_debit_drain_points"], "detail": f"Drain {drain_ratio:.1%} >= {p['bonus_debit_drain_ratio']:.0%}"})
                    did = curr_tx["device_id"]
                    if did and did not in seen_devs:
                        comps.append({"code": "BONUS_NEW_DEVICE", "points": p["bonus_new_device_points"], "detail": f"New device {did} on dormant account"})
                    matches.append({
                        "rule_id": "R04",
                        "trigger_txn": curr_tx,
                        "evidence": [curr_tx],
                        "components": comps,
                    })
                if prev_tx["device_id"]:
                    seen_devs.add(prev_tx["device_id"])
        return matches

    def eval_r05(self) -> List[Dict[str, Any]]:
        """R05: Debit transaction significantly exceeding historical baseline median."""
        matches = []
        r = self.rules["R05"]
        p = r["params"]

        for aid, g in self.tx_df.groupby("account_id"):
            prior_debits: List[float] = []
            for tx in g.to_dict("records"):
                amt = tx["amt_f"]
                if tx["direction"] == "DEBIT":
                    if len(prior_debits) >= p["min_prior_debits"] and amt >= p["min_amount"]:
                        med = float(pd.Series(prior_debits).median())
                        if med > 0 and amt >= p["outlier_multiplier"] * med:
                            mult = amt / med
                            comps = [{"code": "BASE_POINTS", "points": r["base_points"], "detail": f"Debit {amt:.2f} is {mult:.1f}x median {med:.2f}"}]
                            if mult >= p["bonus_extreme_multiplier"]:
                                comps.append({"code": "BONUS_EXTREME_OUTLIER", "points": p["bonus_extreme_points"], "detail": f"Multiplier >= {p['bonus_extreme_multiplier']}x"})
                            mid = tx["merchant_id"]
                            if mid and mid in self.merch_df.index and self.merch_df.loc[mid, "risk_level"] == "HIGH":
                                comps.append({"code": "BONUS_HIGH_RISK_MERCHANT", "points": p["bonus_high_risk_merchant_points"], "detail": "High-risk merchant"})
                            matches.append({
                                "rule_id": "R05",
                                "trigger_txn": tx,
                                "evidence": [tx],
                                "components": comps,
                            })
                    prior_debits.append(amt)
        return matches

    def run(self):
        print("[*] Running detection rules...")
        raw_matches: List[Dict[str, Any]] = []
        raw_matches.extend(self.eval_r01())
        raw_matches.extend(self.eval_r02())
        raw_matches.extend(self.eval_r03())
        raw_matches.extend(self.eval_r04())
        raw_matches.extend(self.eval_r05())
        print(f"[+] Found {len(raw_matches)} raw rule match candidates.")

        # Build alerts: EACH RULE FIRING = ONE ALERT
        alerts, alert_evidence, alert_components = [], [], []
        for idx, m in enumerate(raw_matches, start=1):
            aid = format_alert_id(idx)
            ttx = m["trigger_txn"]
            acc_id = ttx["account_id"]
            cid = self.acc_df.loc[acc_id, "customer_id"]
            comps = list(m["components"])

            # Mitigating adjustment A02: TRUSTED_CUSTOMER
            if self.is_trusted_customer(cid):
                comps.append({
                    "code": "ADJ_TRUSTED_CUSTOMER",
                    "points": self.rules["A02"]["base_points"],
                    "detail": "Verified KYC, low risk tier, tenure >= 3 years",
                })

            raw_score = sum(c["points"] for c in comps)
            risk_score = max(5, min(100, raw_score))
            sev = "CRITICAL" if risk_score >= 85 else ("HIGH" if risk_score >= 70 else ("MEDIUM" if risk_score >= 50 else "LOW"))

            created_ts = format_dt(ttx["dt"] + datetime.timedelta(minutes=5))
            expl = "; ".join(f"{c['code']}: {c['detail']} ({c['points']:+d})" for c in comps)

            alerts.append({
                "alert_id": aid,
                "rule_id": m["rule_id"],
                "trigger_txn_id": ttx["txn_id"],
                "account_id": acc_id,
                "customer_id": cid,
                "created_ts": created_ts,
                "risk_score": risk_score,
                "severity": sev,
                "priority_rank": 0,
                "status": "OPEN",
                "case_id": "",
                "explanation": expl,
                "_dt": ttx["dt"],
            })

            for seq, c in enumerate(comps, start=1):
                alert_components.append({
                    "alert_id": aid,
                    "seq": seq,
                    "component_code": c["code"],
                    "rule_id": m["rule_id"] if c["code"].startswith("BASE") else "",
                    "points": c["points"],
                    "detail": c["detail"],
                })

            for ev_tx in m["evidence"]:
                alert_evidence.append({
                    "alert_id": aid,
                    "txn_id": ev_tx["txn_id"],
                    "role": "TRIGGER" if ev_tx["txn_id"] == ttx["txn_id"] else "SUPPORTING",
                })

        # Priority ranking (1..N permutation)
        sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        alerts.sort(key=lambda x: (sev_order[x["severity"]], -x["risk_score"], x["created_ts"], x["alert_id"]))
        for rank, a in enumerate(alerts, start=1):
            a["priority_rank"] = rank

        # Group into cases: same account within 7 days
        cases, actions = self._group_cases_and_simulate_workflow(alerts)

        # Drop temporary keys
        for a in alerts:
            a.pop("_dt", None)

        print(f"[+] Generated {len(alerts)} alerts, {len(cases)} cases, and {len(actions)} analyst actions.")
        save_table(alerts, "alerts", self.out_dir)
        save_table(alert_evidence, "alert_evidence", self.out_dir)
        save_table(alert_components, "alert_score_components", self.out_dir)
        save_table(cases, "cases", self.out_dir)
        save_table(actions, "analyst_actions", self.out_dir)

    def _group_cases_and_simulate_workflow(self, alerts: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Group alerts on same account within 7 days into cases and simulate triage."""
        # Group alerts by account
        by_acc: Dict[str, List[Dict[str, Any]]] = {}
        for a in alerts:
            by_acc.setdefault(a["account_id"], []).append(a)

        cases, actions = [], []
        case_idx, act_idx = 1, 1

        for aid, acc_alerts in by_acc.items():
            acc_alerts.sort(key=lambda x: x["_dt"])
            # Cluster alerts within 7 days
            clusters: List[List[Dict[str, Any]]] = []
            curr_cluster: List[Dict[str, Any]] = []

            for a in acc_alerts:
                if not curr_cluster:
                    curr_cluster.append(a)
                else:
                    if (a["_dt"] - curr_cluster[-1]["_dt"]).total_seconds() <= 7 * 86400:
                        curr_cluster.append(a)
                    else:
                        clusters.append(curr_cluster)
                        curr_cluster = [a]
            if curr_cluster:
                clusters.append(curr_cluster)

            for cl in clusters:
                cid = format_case_id(case_idx)
                case_idx += 1
                for a in cl:
                    a["case_id"] = cid

                max_score = max(a["risk_score"] for a in cl)
                prio = "P1" if max_score >= 85 else ("P2" if max_score >= 70 else ("P3" if max_score >= 50 else "P4"))
                open_ts = min(a["created_ts"] for a in cl)

                # Deterministic analyst routing
                op_id = f"ANL-{(zlib.crc32(cid.encode()) % 8) + 1:03d}"
                rev_id = f"ANL-{(zlib.crc32(cid.encode()) % 3) + 9:03d}"

                # Workflow actions
                t0 = parse_dt(open_ts)
                actions.append({
                    "action_id": format_action_id(act_idx), "case_id": cid, "alert_id": "",
                    "analyst_id": "ANL-012", "action_type": "ASSIGN", "disposition": "",
                    "action_ts": format_dt(t0 + datetime.timedelta(minutes=15)),
                    "note": f"System assigned case to {op_id}",
                })
                act_idx += 1
                actions.append({
                    "action_id": format_action_id(act_idx), "case_id": cid, "alert_id": "",
                    "analyst_id": op_id, "action_type": "REVIEW_START", "disposition": "",
                    "action_ts": format_dt(t0 + datetime.timedelta(hours=1)),
                    "note": "Analyst began review of correlated alerts",
                })
                act_idx += 1

                # Dispositions
                if max_score >= 70:
                    final_disp = "TRUE_POSITIVE"
                    for a in cl:
                        a["status"] = "CLOSED_TRUE_POSITIVE"
                        actions.append({
                            "action_id": format_action_id(act_idx), "case_id": cid, "alert_id": a["alert_id"],
                            "analyst_id": op_id, "action_type": "DISPOSITION", "disposition": "TRUE_POSITIVE",
                            "action_ts": format_dt(t0 + datetime.timedelta(hours=2)),
                            "note": f"Confirmed high risk pattern (score {a['risk_score']})",
                        })
                        act_idx += 1
                elif max_score < 50:
                    final_disp = "FALSE_POSITIVE"
                    for a in cl:
                        a["status"] = "CLOSED_FALSE_POSITIVE"
                        actions.append({
                            "action_id": format_action_id(act_idx), "case_id": cid, "alert_id": a["alert_id"],
                            "analyst_id": op_id, "action_type": "DISPOSITION", "disposition": "FALSE_POSITIVE",
                            "action_ts": format_dt(t0 + datetime.timedelta(hours=2)),
                            "note": f"Confirmed benign look-alike (score {a['risk_score']})",
                        })
                        act_idx += 1
                else:
                    # 50..69: ESCALATE to risk reviewer
                    actions.append({
                        "action_id": format_action_id(act_idx), "case_id": cid, "alert_id": "",
                        "analyst_id": op_id, "action_type": "ESCALATE", "disposition": "",
                        "action_ts": format_dt(t0 + datetime.timedelta(hours=2)),
                        "note": f"Escalated intermediate score {max_score} to risk reviewer",
                    })
                    act_idx += 1
                    final_disp = "TRUE_POSITIVE" if max_score >= 60 else "FALSE_POSITIVE"
                    status_val = "CLOSED_TRUE_POSITIVE" if final_disp == "TRUE_POSITIVE" else "CLOSED_FALSE_POSITIVE"
                    for a in cl:
                        a["status"] = status_val
                        actions.append({
                            "action_id": format_action_id(act_idx), "case_id": cid, "alert_id": a["alert_id"],
                            "analyst_id": rev_id, "action_type": "DISPOSITION", "disposition": final_disp,
                            "action_ts": format_dt(t0 + datetime.timedelta(hours=4)),
                            "note": f"Risk reviewer confirmed {final_disp}",
                        })
                        act_idx += 1

                close_ts = format_dt(t0 + datetime.timedelta(hours=5))
                actions.append({
                    "action_id": format_action_id(act_idx), "case_id": cid, "alert_id": "",
                    "analyst_id": op_id if max_score >= 70 or max_score < 50 else rev_id,
                    "action_type": "CLOSE", "disposition": "",
                    "action_ts": close_ts, "note": f"Case closed with disposition {final_disp}",
                })
                act_idx += 1

                cases.append({
                    "case_id": cid,
                    "primary_account_id": aid,
                    "opened_ts": open_ts,
                    "closed_ts": close_ts,
                    "alert_count": len(cl),
                    "case_score": max_score,
                    "priority": prio,
                    "status": "CLOSED",
                    "assigned_analyst_id": op_id if max_score >= 70 or max_score < 50 else rev_id,
                    "final_disposition": final_disp,
                })
        return cases, actions

def main():
    parser = argparse.ArgumentParser(description="Stage 2: Evaluate Rules and Triage Cases")
    parser.add_argument("--out", type=str, default="output", help="Output directory")
    args = parser.parse_args()

    engine = RulesEngine(out_dir=args.out)
    engine.run()

if __name__ == "__main__":
    main()
