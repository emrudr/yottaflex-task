"""Transaction generator: background transactions, exact budget allocation, and balance sweep."""

from __future__ import annotations

import datetime
import math
import random
from typing import Any, Dict, List, Tuple

from config import (
    CHANNELS,
    DATA_END,
    DATA_START,
    format_transfer_id,
    format_txn_id,
)

DT_FMT = "%Y-%m-%d %H:%M:%S"
DATE_FMT = "%Y-%m-%d"

def parse_dt(s: str) -> datetime.datetime:
    return datetime.datetime.strptime(s, DT_FMT)

def format_dt(dt: datetime.datetime) -> str:
    return dt.strftime(DT_FMT)

def allocate_event_counts(n_accounts: int, budget: int, rng: random.Random) -> List[int]:
    """Allocate exact background transaction budget across accounts with min 6 each."""
    min_per_acc = 6
    if budget < n_accounts * min_per_acc:
        raise ValueError(f"Background budget {budget} insufficient for {n_accounts} accounts with min {min_per_acc}")

    counts = [min_per_acc] * n_accounts
    remaining = budget - (n_accounts * min_per_acc)

    # Largest remainder allocation
    weights = [rng.uniform(1.0, 3.0) for _ in range(n_accounts)]
    total_w = sum(weights)
    quotas = [(w / total_w) * remaining for w in weights]
    floors = [int(math.floor(q)) for q in quotas]
    remainders = [(quotas[i] - floors[i], i) for i in range(n_accounts)]

    for i in range(n_accounts):
        counts[i] += floors[i]

    allocated_remainder = sum(floors)
    leftover = remaining - allocated_remainder
    remainders.sort(reverse=True, key=lambda x: x[0])
    for i in range(leftover):
        counts[remainders[i][1]] += 1

    return counts

def generate_account_background_txns(
    acc: Dict[str, Any],
    count: int,
    cutoff_ts: str,
    merchants: List[Dict[str, Any]],
    device_id: str,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    """Generate background events placed evenly across active window slices."""
    aid = acc["account_id"]
    t_start = max(parse_dt(DATA_START), parse_dt(f"{acc['open_date']} 09:00:00"))
    t_end = parse_dt(cutoff_ts)
    total_sec = max(3600, int((t_end - t_start).total_seconds()))
    slice_sec = total_sec / count

    running_bal = float(acc["starting_balance"])
    od_limit = float(acc["overdraft_limit"])
    txns = []

    for k in range(count):
        s_start = int(k * slice_sec)
        s_end = int((k + 1) * slice_sec)
        offset = rng.randint(s_start, max(s_start, s_end - 60))
        txn_ts = format_dt(t_start + datetime.timedelta(seconds=offset))

        is_debit = (k < 5) or (rng.random() < 0.65)
        avail = running_bal + od_limit

        if is_debit and avail > 25.0:
            max_limit = 300.0 if cutoff_ts < DATA_END else 3500.0
            raw_amt = round(rng.uniform(50.0, max_limit), 2)
            amt = round(min(raw_amt, 0.40 * avail), 2)
            if amt < 10.0:
                is_debit = False  # Convert to credit
            else:
                running_bal -= amt
                m = rng.choice(merchants)
                txns.append({
                    "account_id": aid,
                    "txn_ts": txn_ts,
                    "txn_type": "POS_PURCHASE" if rng.random() < 0.6 else "UPI_PAYMENT",
                    "direction": "DEBIT",
                    "amount": amt,
                    "channel": "POS" if rng.random() < 0.5 else "UPI",
                    "merchant_id": m["merchant_id"],
                    "device_id": device_id,
                    "counterparty_account_id": "",
                    "transfer_id": "",
                })
        elif is_debit:
            is_debit = False  # Convert to credit when balance is low

        if not is_debit:
            amt = round(rng.uniform(500.0, 15000.0), 2)
            running_bal += amt
            txns.append({
                "account_id": aid,
                "txn_ts": txn_ts,
                "txn_type": "CASH_DEPOSIT" if rng.random() < 0.7 else "SALARY_CREDIT",
                "direction": "CREDIT",
                "amount": amt,
                "channel": "BRANCH" if rng.random() < 0.5 else "WEB",
                "merchant_id": "",
                "device_id": device_id,
                "counterparty_account_id": "",
                "transfer_id": "",
            })

    return txns

def generate_background_transfer_pairs(
    accounts: List[Dict[str, Any]],
    n_pairs: int,
    start_trf_id: int,
    dormant_cutoffs: Dict[str, str],
    dev_map: Dict[str, str],
    rng: random.Random,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generate routine background transfer pairs with source_account_id < dest_account_id."""
    active_accs = [
        a for a in accounts
        if dormant_cutoffs.get(a["account_id"], DATA_END) == DATA_END and a["open_date"] <= "2026-02-01"
    ]
    active_accs.sort(key=lambda x: x["account_id"])
    if len(active_accs) < 2 or n_pairs <= 0:
        return [], []

    events, links = [], []
    t_base = parse_dt("2026-02-01 09:00:00")
    src_pool = [a for a in active_accs if float(a["starting_balance"]) >= 40000.0]
    if not src_pool:
        src_pool = active_accs[:max(1, len(active_accs) // 2)]
    rng.shuffle(src_pool)

    for i in range(n_pairs):
        src = src_pool[i % len(src_pool)]
        valid_dsts = [d for d in active_accs if d["account_id"] > src["account_id"]]
        if not valid_dsts:
            src, dst = sorted(rng.sample(active_accs, 2), key=lambda x: x["account_id"])
        else:
            dst = rng.choice(valid_dsts)
        trfid = format_transfer_id(start_trf_id + i)

        dt_deb = t_base + datetime.timedelta(seconds=rng.randint(0, 180 * 86400))
        ts_deb = format_dt(dt_deb)
        ts_crd = format_dt(dt_deb + datetime.timedelta(minutes=2))
        raw_amt = round(rng.uniform(150.0, 3500.0), 2)
        dev_id = dev_map.get(src["customer_id"], "")

        ev_deb = {
            "account_id": src["account_id"], "txn_ts": ts_deb, "txn_type": "NEFT_TRANSFER_OUT",
            "direction": "DEBIT", "amount": raw_amt, "channel": "WEB", "merchant_id": "",
            "device_id": dev_id, "counterparty_account_id": dst["account_id"], "transfer_id": trfid,
            "is_bg_transfer": True, "raw_amount": raw_amt,
        }
        ev_crd = {
            "account_id": dst["account_id"], "txn_ts": ts_crd, "txn_type": "TRANSFER_IN",
            "direction": "CREDIT", "amount": raw_amt, "channel": "WEB", "merchant_id": "",
            "device_id": "", "counterparty_account_id": src["account_id"], "transfer_id": trfid,
            "is_bg_transfer": True, "raw_amount": raw_amt,
        }
        pair_state = {"raw_amount": raw_amt, "is_converted": False, "amt": raw_amt}
        ev_deb["pair_state"] = pair_state
        ev_crd["pair_state"] = pair_state

        links.append({
            "transfer_id": trfid, "source_account_id": src["account_id"], "dest_account_id": dst["account_id"],
            "debit_txn_ref": ev_deb, "credit_txn_ref": ev_crd, "amount": raw_amt,
            "initiated_ts": ts_deb, "settled_ts": ts_crd, "status": "SETTLED", "pair_state": pair_state,
        })
        events.extend([ev_deb, ev_crd])
    return events, links

def run_balance_sweep(
    all_events: List[Dict[str, Any]],
    accounts: List[Dict[str, Any]],
    transfer_links: List[Dict[str, Any]],
    ground_truth: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Sort all events, run chronological balance sweep, and assign final TXN IDs."""
    all_events.sort(key=lambda x: (x["txn_ts"], x["account_id"]))
    acc_map = {a["account_id"]: a for a in accounts}
    bal_map = {a["account_id"]: float(a["starting_balance"]) for a in accounts}
    od_map = {a["account_id"]: float(a["overdraft_limit"]) for a in accounts}

    final_txns = []
    for idx, ev in enumerate(all_events, start=1):
        tid = format_txn_id(idx)
        ev["txn_id"] = tid
        aid = ev["account_id"]
        bb = bal_map[aid]

        if ev.get("is_dormant_drain"):
            ev["amount"] = round(0.90 * bb, 2)

        if ev.get("is_bg_transfer"):
            ps = ev["pair_state"]
            if ev["direction"] == "DEBIT":
                avail = bb + od_map[aid]
                max_amt = round(0.30 * avail, 2)
                resolved = min(ps["raw_amount"], max_amt)
                if resolved < 100.00:
                    ps["is_converted"] = True
                    ev["txn_type"] = "CASH_DEPOSIT"
                    ev["direction"] = "CREDIT"
                    ev["amount"] = 500.0
                    ev["counterparty_account_id"] = ""
                    ev["transfer_id"] = ""
                else:
                    ps["amt"] = resolved
                    ev["amount"] = resolved
            else:
                if ps["is_converted"]:
                    ev["txn_type"] = "CASH_DEPOSIT"
                    ev["direction"] = "CREDIT"
                    ev["amount"] = 500.0
                    ev["counterparty_account_id"] = ""
                    ev["transfer_id"] = ""
                else:
                    ev["amount"] = ps["amt"]

        amt = float(ev["amount"])
        direction = ev["direction"]

        if direction == "CREDIT":
            ba = round(bb + amt, 2)
        else:
            ba = round(bb - amt, 2)
            is_anomaly = ev.get("is_injected_anomaly", False)
            if not is_anomaly and ba < -od_map[aid] - 0.01:
                raise ValueError(
                    f"Floor breach on account {aid}: txn {tid} debit {amt} reduced balance to {ba} below overdraft limit -{od_map[aid]}"
                )

        ev["balance_before"] = f"{bb:.2f}"
        ev["balance_after"] = f"{ba:.2f}"
        bal_map[aid] = ba

        final_txns.append({
            "txn_id": tid,
            "account_id": aid,
            "txn_ts": ev["txn_ts"],
            "txn_type": ev["txn_type"],
            "direction": direction,
            "amount": f"{amt:.2f}",
            "balance_before": ev["balance_before"],
            "balance_after": ev["balance_after"],
            "channel": ev["channel"],
            "merchant_id": ev.get("merchant_id", ""),
            "device_id": ev.get("device_id", ""),
            "counterparty_account_id": ev.get("counterparty_account_id", ""),
            "transfer_id": ev.get("transfer_id", ""),
        })

    # Resolve transfer links references (discarding converted pairs)
    resolved_links = []
    for trf in transfer_links:
        ps = trf.get("pair_state")
        if ps and ps.get("is_converted"):
            continue
        trf["debit_txn_id"] = trf.pop("debit_txn_ref")["txn_id"]
        trf["credit_txn_id"] = trf.pop("credit_txn_ref")["txn_id"]
        amt_val = ps["amt"] if ps else trf["amount"]
        trf["amount"] = f"{float(amt_val):.2f}"
        trf.pop("pair_state", None)
        resolved_links.append(trf)

    # Resolve ground truth trigger references
    for gt in ground_truth:
        ref = gt.pop("trigger_event_ref", None)
        gt["trigger_txn_id"] = ref["txn_id"] if ref and "txn_id" in ref else ""
        if isinstance(gt["entity_id"], dict) and "txn_id" in gt["entity_id"]:
            gt["entity_id"] = gt["entity_id"]["txn_id"]

    return final_txns, resolved_links

def build_account_devices(
    transactions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build account_devices bridge table from executed transaction history."""
    records: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for tx in transactions:
        aid = tx["account_id"]
        did = tx["device_id"]
        if not did:
            continue
        key = (aid, did)
        ts = tx["txn_ts"]
        if key not in records:
            records[key] = {
                "account_id": aid,
                "device_id": did,
                "first_seen_ts": ts,
                "last_seen_ts": ts,
                "txn_count": 1,
            }
        else:
            records[key]["last_seen_ts"] = ts
            records[key]["txn_count"] += 1

    account_devices = []
    for r in records.values():
        is_active = r["last_seen_ts"] >= "2026-08-01 00:00:00"
        r["link_status"] = "ACTIVE" if is_active else "INACTIVE"
        account_devices.append(r)

    account_devices.sort(key=lambda x: (x["account_id"], x["device_id"]))
    return account_devices

def generate_transactions_dataset(
    master: Dict[str, Any],
    scenario_data: Dict[str, Any],
    target_txns: int,
    seed: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generate exact transaction budget, execute balance sweep, and build bridge tables."""
    rng = random.Random(f"{seed}:background")
    accounts = master["accounts"]
    scenario_events = scenario_data["events"]
    transfer_links = scenario_data["transfer_links"]
    ground_truth = scenario_data["ground_truth"]
    dormant_cutoffs = scenario_data["dormant_cutoff_map"]

    bg_budget_total = target_txns - len(scenario_events)
    n_pairs = int(0.03 * bg_budget_total // 2)
    indiv_budget = bg_budget_total - (2 * n_pairs)
    counts = allocate_event_counts(len(accounts), indiv_budget, rng)

    # Customer device mapping
    dev_map = {}
    for d in master["devices"]:
        cid = d.get("owner_customer_id")
        if cid and cid not in dev_map:
            dev_map[cid] = d["device_id"]

    bg_events = []
    for idx, acc in enumerate(accounts):
        aid = acc["account_id"]
        cid = acc["customer_id"]
        dev_id = dev_map.get(cid, master["devices"][0]["device_id"])
        cutoff = dormant_cutoffs.get(aid, DATA_END)
        cnt = counts[idx]
        txs = generate_account_background_txns(acc, cnt, cutoff, master["merchants"], dev_id, rng)
        bg_events.extend(txs)

    trf_events, bg_links = generate_background_transfer_pairs(
        accounts, n_pairs, len(transfer_links) + 1, dormant_cutoffs, dev_map, rng
    )
    all_events = scenario_events + trf_events + bg_events
    all_links = transfer_links + bg_links
    final_txns, resolved_links = run_balance_sweep(all_events, accounts, all_links, ground_truth)
    account_devices = build_account_devices(final_txns)

    return final_txns, resolved_links, account_devices
