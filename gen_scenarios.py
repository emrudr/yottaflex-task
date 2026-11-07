"""Planted suspicious patterns (TRUE), benign look-alikes (FP), and transaction anomalies."""

from __future__ import annotations

import datetime
import random
from typing import Any, Dict, List, Set, Tuple

from config import (
    DATE_FMT,
    format_device_id,
    format_scenario_id,
    format_status_event_id,
    format_transfer_id,
)

DT_FMT = "%Y-%m-%d %H:%M:%S"

def parse_dt(s: str) -> datetime.datetime:
    return datetime.datetime.strptime(s, DT_FMT)

def format_dt(dt: datetime.datetime) -> str:
    return dt.strftime(DT_FMT)

def make_ev(aid: str, ts: str, ttype: str, direction: str, amt: float, chan: str = "MOBILE_APP", mid: str = "", did: str = "", cpty: str = "", trfid: str = "", **kwargs) -> Dict[str, Any]:
    ev = {"account_id": aid, "txn_ts": ts, "txn_type": ttype, "direction": direction, "amount": amt, "channel": chan, "merchant_id": mid, "device_id": did, "counterparty_account_id": cpty, "transfer_id": trfid}
    ev.update(kwargs)
    return ev

class ScenarioBuilder:
    def __init__(self, master: Dict[str, Any], cfg: Dict[str, Any], seed: int):
        self.master = master
        self.counts = cfg["scenario_counts"]
        self.rng = random.Random(f"{seed}:scenarios")
        self.accounts = master["accounts"]
        self.customers = {c["customer_id"]: c for c in master["customers"]}
        self.devices = master["devices"]
        self.merchants = master["merchants"]

        self.trusted_aids, self.nontrusted_aids = [], []
        for a in self.accounts:
            c = self.customers[a["customer_id"]]
            onboard = datetime.datetime.strptime(c["onboarding_date"], DATE_FMT).date()
            if onboard <= datetime.date(2023, 10, 31) and c["kyc_status"] == "VERIFIED" and c["kyc_risk_tier"] == "LOW":
                self.trusted_aids.append(a["account_id"])
            else:
                self.nontrusted_aids.append(a["account_id"])

        self.dormant_cutoff_map: Dict[str, str] = {}
        self.events, self.transfer_links, self.ground_truth = [], [], []
        self.used_accounts: Set[str] = set()
        self.trf_counter, self.scn_counter = 1, 1
        self.ase_counter = len(master["account_status_events"]) + 1

    def get_account_device(self, aid: str) -> str:
        cid = next(a["customer_id"] for a in self.accounts if a["account_id"] == aid)
        devs = [d["device_id"] for d in self.devices if d["owner_customer_id"] == cid]
        return devs[0] if devs else self.devices[0]["device_id"]

    def add_gt(self, stype: str, label: str, aid: str, trig_ev: Any, rule: str, dec: str, issue: str = "", etype: str = "ACCOUNT", eid: Any = None):
        self.ground_truth.append({
            "scenario_id": format_scenario_id(self.scn_counter),
            "scenario_type": stype, "label": label, "account_id": aid,
            "trigger_event_ref": trig_ev, "expected_rule_id": rule, "expected_decision": dec,
            "issue_type": issue, "entity_type": etype, "entity_id": eid if eid else aid,
        })
        self.scn_counter += 1

    def plan_dormant_accounts(self) -> Tuple[List[str], List[str]]:
        avail_nt = [a for a in self.nontrusted_aids if a not in self.used_accounts]
        avail_tr = [a for a in self.trusted_aids if a not in self.used_accounts]
        true_aids = avail_nt[: self.counts["TRUE_DORMANT"]]
        fp_aids = avail_tr[: self.counts["FP_DORMANT"]]
        self.used_accounts.update(true_aids + fp_aids)
        for aid in true_aids + fp_aids:
            self.dormant_cutoff_map[aid] = "2026-01-10 12:00:00"
        for aid in true_aids:
            for a in self.accounts:
                if a["account_id"] == aid:
                    a["starting_balance"] = "60000.00"
        return true_aids, fp_aids

    def build_dormant_scenarios(self, true_aids: List[str], fp_aids: List[str]):
        shared_devs = [d["device_id"] for d in self.devices if not d["owner_customer_id"]]
        for aid in true_aids:
            self._add_status_event(aid, "ACTIVE", "DORMANT", "2026-07-15 00:00:00", "INACTIVITY_180D")
            dev = shared_devs[0] if shared_devs else self.devices[0]["device_id"]
            ev = make_ev(aid, "2026-07-20 14:15:00", "NEFT_TRANSFER_OUT", "DEBIT", 25000.0, did=dev, is_dormant_drain=True)
            self.events.append(ev)
            self._add_status_event(aid, "DORMANT", "ACTIVE", "2026-07-20 14:15:00", "REACTIVATED_BY_ACTIVITY")
            self.add_gt("TRUE_DORMANT", "SUSPICIOUS", aid, ev, "R04", "TRUE_POSITIVE")

        for aid in fp_aids:
            self._add_status_event(aid, "ACTIVE", "DORMANT", "2026-07-15 00:00:00", "INACTIVITY_180D")
            ev = make_ev(aid, "2026-07-20 10:00:00", "CASH_DEPOSIT", "CREDIT", 20000.0, chan="BRANCH")
            self.events.append(ev)
            self._add_status_event(aid, "DORMANT", "ACTIVE", "2026-07-20 10:00:00", "REACTIVATED_BY_ACTIVITY")
            self.add_gt("FP_DORMANT", "BENIGN_LOOKALIKE", aid, ev, "R04", "FALSE_POSITIVE")

    def _add_status_event(self, aid: str, from_s: str, to_s: str, ts: str, reason: str):
        self.master["account_status_events"].append({
            "event_id": format_status_event_id(self.ase_counter),
            "account_id": aid, "from_status": from_s, "to_status": to_s, "effective_ts": ts, "reason": reason,
        })
        self.ase_counter += 1

    def build_velocity_scenarios(self):
        avail_nt = [a for a in self.nontrusted_aids if a not in self.used_accounts]
        avail_tr = [a for a in self.trusted_aids if a not in self.used_accounts]
        for i in range(min(self.counts["TRUE_VELOCITY"], len(avail_nt))):
            aid = avail_nt[i]
            self.used_accounts.add(aid)
            base_dt = parse_dt("2026-08-10 14:00:00") + datetime.timedelta(hours=i * 2)
            dev = self.get_account_device(aid)
            self.events.append(make_ev(aid, format_dt(base_dt - datetime.timedelta(hours=2)), "SALARY_CREDIT", "CREDIT", 100000.0, chan="WEB", did=dev))
            trig_ev = None
            for step in range(10):
                ev = make_ev(aid, format_dt(base_dt + datetime.timedelta(minutes=step * 3)), "UPI_PAYMENT", "DEBIT", 6000.0, chan="UPI", mid=self.merchants[0]["merchant_id"], did=dev)
                self.events.append(ev)
                trig_ev = ev
            self.add_gt("TRUE_VELOCITY", "SUSPICIOUS", aid, trig_ev, "R01", "TRUE_POSITIVE")

        for i in range(min(self.counts["FP_VELOCITY"], len(avail_tr))):
            aid = avail_tr[i]
            self.used_accounts.add(aid)
            base_dt = parse_dt("2026-08-15 10:00:00") + datetime.timedelta(hours=i * 2)
            dev = self.get_account_device(aid)
            self.events.append(make_ev(aid, format_dt(base_dt - datetime.timedelta(hours=2)), "CASH_DEPOSIT", "CREDIT", 20000.0, chan="BRANCH"))
            trig_ev = None
            for step in range(6):
                ev = make_ev(aid, format_dt(base_dt + datetime.timedelta(minutes=step * 5)), "UPI_PAYMENT", "DEBIT", 500.0, chan="UPI", mid=self.merchants[0]["merchant_id"], did=dev)
                self.events.append(ev)
                trig_ev = ev
            self.add_gt("FP_VELOCITY", "BENIGN_LOOKALIKE", aid, trig_ev, "R01", "FALSE_POSITIVE")

    def build_new_device_scenarios(self):
        avail_nt = [a for a in self.nontrusted_aids if a not in self.used_accounts]
        avail_tr = [a for a in self.trusted_aids if a not in self.used_accounts]
        shared_devs = [d["device_id"] for d in self.devices if not d["owner_customer_id"]]

        for i in range(min(self.counts["TRUE_NEW_DEVICE"], len(avail_nt))):
            aid = avail_nt[i]
            self.used_accounts.add(aid)
            dev = shared_devs[i % len(shared_devs)] if shared_devs else self.devices[0]["device_id"]
            ts = format_dt(parse_dt("2026-08-20 11:00:00") + datetime.timedelta(hours=i * 2))
            self.events.append(make_ev(aid, format_dt(parse_dt(ts) - datetime.timedelta(hours=3)), "SALARY_CREDIT", "CREDIT", 100000.0, chan="WEB", did=self.get_account_device(aid)))
            ev = make_ev(aid, ts, "NEFT_TRANSFER_OUT", "DEBIT", 60000.0, did=dev)
            self.events.append(ev)
            self.add_gt("TRUE_NEW_DEVICE", "SUSPICIOUS", aid, ev, "R02", "TRUE_POSITIVE")

        dev_counter = len(self.devices) + 1
        for i in range(min(self.counts["FP_NEW_DEVICE"], len(avail_tr))):
            aid = avail_tr[i]
            self.used_accounts.add(aid)
            cid = next(a["customer_id"] for a in self.accounts if a["account_id"] == aid)
            clean_dev = format_device_id(dev_counter); dev_counter += 1
            self.master["devices"].append({"device_id": clean_dev, "device_type": "ANDROID", "os_family": "ANDROID", "fingerprint_hash": f"fpclean{i:08d}", "is_emulator": False, "status": "ACTIVE", "first_registered_date": "2026-08-25", "owner_customer_id": cid})
            ts = format_dt(parse_dt("2026-08-25 14:00:00") + datetime.timedelta(hours=i * 2))
            self.events.append(make_ev(aid, format_dt(parse_dt(ts) - datetime.timedelta(hours=2)), "CASH_DEPOSIT", "CREDIT", 50000.0, chan="BRANCH"))
            ev = make_ev(aid, ts, "NEFT_TRANSFER_OUT", "DEBIT", 18000.0, did=clean_dev)
            self.events.append(ev)
            self.add_gt("FP_NEW_DEVICE", "BENIGN_LOOKALIKE", aid, ev, "R02", "FALSE_POSITIVE")

    def _add_transfer(self, a_src: str, a_dst: str, amt: float, t_deb: str, t_crd: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        trfid = format_transfer_id(self.trf_counter); self.trf_counter += 1
        ev_deb = make_ev(a_src, t_deb, "NEFT_TRANSFER_OUT", "DEBIT", amt, did=self.get_account_device(a_src), cpty=a_dst, trfid=trfid)
        ev_crd = make_ev(a_dst, t_crd, "TRANSFER_IN", "CREDIT", amt, cpty=a_src, trfid=trfid)
        self.events.extend([ev_deb, ev_crd])
        self.transfer_links.append({"transfer_id": trfid, "source_account_id": a_src, "dest_account_id": a_dst, "debit_txn_ref": ev_deb, "credit_txn_ref": ev_crd, "amount": amt, "initiated_ts": t_deb, "settled_ts": t_crd, "status": "SETTLED"})
        return ev_deb, ev_crd

    def build_circular_scenarios(self):
        avail_nt = [a for a in self.nontrusted_aids if a not in self.used_accounts]
        for i in range(self.counts["TRUE_CIRCULAR"]):
            if len(avail_nt) < 3: break
            a1, a2, a3 = avail_nt.pop(0), avail_nt.pop(0), avail_nt.pop(0)
            self.used_accounts.update([a1, a2, a3])
            t0 = parse_dt("2026-09-01 09:00:00") + datetime.timedelta(days=i * 2)
            self.events.append(make_ev(a1, format_dt(t0 - datetime.timedelta(hours=2)), "CASH_DEPOSIT", "CREDIT", 40000.0, chan="BRANCH"))
            self._add_transfer(a1, a2, 18000.0, format_dt(t0), format_dt(t0 + datetime.timedelta(minutes=5)))
            self._add_transfer(a2, a3, 17800.0, format_dt(t0 + datetime.timedelta(hours=1)), format_dt(t0 + datetime.timedelta(hours=1, minutes=5)))
            ev3_deb, _ = self._add_transfer(a3, a1, 17600.0, format_dt(t0 + datetime.timedelta(hours=2)), format_dt(t0 + datetime.timedelta(hours=2, minutes=5)))
            self.add_gt("TRUE_CIRCULAR", "SUSPICIOUS", a1, ev3_deb, "R03", "TRUE_POSITIVE")

        multi_acc = [aids[:2] for aids in [[a["account_id"] for a in self.accounts if a["customer_id"] == c["customer_id"]] for c in self.customers.values()] if len(aids) >= 2 and aids[0] in self.trusted_aids]
        for i in range(min(self.counts["FP_CIRCULAR"], len(multi_acc))):
            a1, a2 = multi_acc[i]
            self.used_accounts.update([a1, a2])
            t0 = parse_dt("2026-09-10 10:00:00") + datetime.timedelta(days=i * 2)
            self.events.append(make_ev(a1, format_dt(t0 - datetime.timedelta(hours=2)), "CASH_DEPOSIT", "CREDIT", 50000.0, chan="BRANCH"))
            self._add_transfer(a1, a2, 12000.0, format_dt(t0), format_dt(t0 + datetime.timedelta(minutes=5)))
            ev2_deb, _ = self._add_transfer(a2, a1, 12000.0, format_dt(t0 + datetime.timedelta(hours=2)), format_dt(t0 + datetime.timedelta(hours=2, minutes=5)))
            self.add_gt("FP_CIRCULAR", "BENIGN_LOOKALIKE", a2, ev2_deb, "R03", "FALSE_POSITIVE")

    def build_outlier_scenarios(self):
        avail_nt = [a for a in self.nontrusted_aids if a not in self.used_accounts]
        high_m = [m["merchant_id"] for m in self.merchants if m["risk_level"] == "HIGH"]
        for i in range(min(self.counts["TRUE_OUTLIER"], len(avail_nt))):
            aid = avail_nt[i]
            self.used_accounts.add(aid)
            t0 = parse_dt("2026-09-20 12:00:00") + datetime.timedelta(hours=i * 2)
            m_id = high_m[i % len(high_m)] if high_m else self.merchants[0]["merchant_id"]
            self.events.append(make_ev(aid, format_dt(t0 - datetime.timedelta(hours=3)), "CASH_DEPOSIT", "CREDIT", 100000.0, chan="BRANCH"))
            ev = make_ev(aid, format_dt(t0), "POS_PURCHASE", "DEBIT", 85000.0, chan="POS", mid=m_id, did=self.get_account_device(aid))
            self.events.append(ev)
            self.add_gt("TRUE_OUTLIER", "SUSPICIOUS", aid, ev, "R05", "TRUE_POSITIVE")

    def build_transaction_anomalies(self):
        avail = [a["account_id"] for a in self.accounts if a["account_id"] not in self.used_accounts]
        for i in range(self.counts["INJ_CLOSED_ACCOUNT_TXN"]):
            aid = avail.pop(0)
            self.used_accounts.add(aid)
            self.dormant_cutoff_map[aid] = "2026-08-01 12:00:00"
            for a in self.accounts:
                if a["account_id"] == aid: a["close_date"], a["status"] = "2026-08-01", "CLOSED"
            self._add_status_event(aid, "ACTIVE", "CLOSED", "2026-08-01 17:00:00", "CLOSED_BY_CUSTOMER")
            ev = make_ev(aid, f"2026-09-{(i % 20) + 1:02d} 11:30:00", "ATM_WITHDRAWAL", "DEBIT", 1000.0, chan="ATM", is_injected_anomaly=True)
            self.events.append(ev)
            self.add_gt("INJ_CLOSED_ACCOUNT_TXN", "DATA_QUALITY_ISSUE", aid, ev, "", "DATA_QUALITY_ISSUE", issue="TXN_ON_CLOSED_ACCOUNT", etype="TRANSACTION", eid=ev)

        for i in range(self.counts["INJ_NEGATIVE_BALANCE_NO_OD"]):
            aid = avail.pop(0)
            self.used_accounts.add(aid)
            self.dormant_cutoff_map[aid] = "2026-09-01 12:00:00"
            ev = make_ev(aid, f"2026-09-{(i % 20) + 1:02d} 15:00:00", "ATM_WITHDRAWAL", "DEBIT", 250000.0, chan="ATM", is_injected_anomaly=True)
            self.events.append(ev)
            self.add_gt("INJ_NEGATIVE_BALANCE_NO_OD", "DATA_QUALITY_ISSUE", aid, ev, "", "DATA_QUALITY_ISSUE", issue="NEGATIVE_BALANCE_NO_OD", etype="TRANSACTION", eid=ev)

        for i in range(self.counts["INJ_TRANSFER_LEG_MISMATCH"]):
            a1, a2 = avail.pop(0), avail.pop(0)
            self.used_accounts.update([a1, a2])
            trfid = format_transfer_id(self.trf_counter); self.trf_counter += 1
            day_str = f"2026-09-{(i % 20) + 1:02d}"
            self.events.append(make_ev(a1, f"{day_str} 08:00:00", "CASH_DEPOSIT", "CREDIT", 50000.0, chan="BRANCH"))
            ev_deb = make_ev(a1, f"{day_str} 10:00:00", "NEFT_TRANSFER_OUT", "DEBIT", 10000.0, did=self.get_account_device(a1), cpty=a2, trfid=trfid)
            ev_crd = make_ev(a2, f"{day_str} 10:05:00", "TRANSFER_IN", "CREDIT", 9500.0, cpty=a1, trfid=trfid)
            self.events.extend([ev_deb, ev_crd])
            self.transfer_links.append({"transfer_id": trfid, "source_account_id": a1, "dest_account_id": a2, "debit_txn_ref": ev_deb, "credit_txn_ref": ev_crd, "amount": 10000.0, "initiated_ts": f"{day_str} 10:00:00", "settled_ts": f"{day_str} 10:05:00", "status": "SETTLED"})
            self.add_gt("INJ_TRANSFER_LEG_MISMATCH", "DATA_QUALITY_ISSUE", a1, ev_deb, "", "DATA_QUALITY_ISSUE", issue="TRANSFER_LEG_MISMATCH", etype="TRANSFER", eid=trfid)

    def build_all(self) -> Dict[str, Any]:
        true_d, fp_d = self.plan_dormant_accounts()
        self.build_dormant_scenarios(true_d, fp_d)
        self.build_velocity_scenarios()
        self.build_new_device_scenarios()
        self.build_circular_scenarios()
        self.build_outlier_scenarios()
        self.build_transaction_anomalies()
        return {"events": self.events, "transfer_links": self.transfer_links, "ground_truth": self.ground_truth, "dormant_cutoff_map": self.dormant_cutoff_map}
