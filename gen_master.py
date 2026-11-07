"""Master data generator: creates customers, accounts, merchants, devices, and analysts."""

from __future__ import annotations

import datetime
import hashlib
import random
from typing import Any, Dict, List, Tuple

from config import (
    ACCOUNT_TYPES,
    ANALYST_ROLES,
    CITIES,
    CURRENCY,
    CUSTOMER_SEGMENT_WEIGHTS,
    CUSTOMER_SEGMENTS,
    DATA_START,
    DEVICE_TYPES,
    FIRST_NAMES,
    KYC_RISK_TIER_WEIGHTS,
    KYC_RISK_TIERS,
    KYC_STATUS_WEIGHTS,
    KYC_STATUSES,
    LAST_NAMES,
    MERCHANT_CATEGORIES,
    MERCHANT_CATEGORY_WEIGHTS,
    MERCHANT_RISK_MAP,
    OS_FAMILIES,
    format_account_id,
    format_analyst_id,
    format_customer_id,
    format_device_id,
    format_merchant_id,
    format_status_event_id,
)

DATE_FMT = "%Y-%m-%d"
DT_FMT = "%Y-%m-%d %H:%M:%S"

def generate_customers(n_customers: int, seed: int) -> List[Dict[str, Any]]:
    """Generate synthetic customer profiles with deterministic demographics and KYC."""
    rng = random.Random(f"{seed}:customers")
    customers = []
    base_dob = datetime.date(1960, 1, 1)
    base_onboard = datetime.date(2020, 1, 1)

    for i in range(1, n_customers + 1):
        cid = format_customer_id(i)
        fn = rng.choice(FIRST_NAMES)
        ln = rng.choice(LAST_NAMES)
        dob = base_dob + datetime.timedelta(days=rng.randint(0, 14000))
        # Ensure a good portion have tenure >= 3 years (onboarded before Oct 2023)
        onboard = base_onboard + datetime.timedelta(days=rng.randint(0, 1800))
        seg = rng.choices(CUSTOMER_SEGMENTS, weights=CUSTOMER_SEGMENT_WEIGHTS, k=1)[0]
        kyc = rng.choices(KYC_STATUSES, weights=KYC_STATUS_WEIGHTS, k=1)[0]
        tier = rng.choices(KYC_RISK_TIERS, weights=KYC_RISK_TIER_WEIGHTS, k=1)[0]

        v_date = onboard.strftime(DATE_FMT) if kyc != "PENDING" else ""
        exp_date = (onboard + datetime.timedelta(days=1095)).strftime(DATE_FMT) if kyc == "VERIFIED" else (
            "2025-12-31" if kyc == "EXPIRED" else ""
        )

        customers.append({
            "customer_id": cid,
            "full_name": f"{fn} {ln}",
            "date_of_birth": dob.strftime(DATE_FMT),
            "email": f"cus-{i:06d}@example.test",
            "city": rng.choice(CITIES),
            "segment": seg,
            "kyc_status": kyc,
            "kyc_risk_tier": tier,
            "kyc_verified_date": v_date,
            "kyc_expiry_date": exp_date,
            "onboarding_date": onboard.strftime(DATE_FMT),
        })
    return customers

def generate_accounts(customers: List[Dict[str, Any]], n_accounts: int, seed: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generate accounts and their initial OPENED status events."""
    rng = random.Random(f"{seed}:accounts")
    accounts, status_events = [], []
    ase_counter = 1

    # 1. Primary account for every customer
    for c in customers:
        aid = format_account_id(c["customer_id"], 1)
        atype = "CURRENT" if c["segment"] == "BUSINESS" else ("SALARY" if c["segment"] == "SALARIED" else "SAVINGS")
        od = 50000.0 if atype == "CURRENT" else 0.0
        bal = round(rng.uniform(15000.0, 120000.0), 2)
        accounts.append({
            "account_id": aid,
            "customer_id": c["customer_id"],
            "account_type": atype,
            "open_date": c["onboarding_date"],
            "close_date": "",
            "status": "ACTIVE",
            "starting_balance": f"{bal:.2f}",
            "overdraft_limit": f"{od:.2f}",
            "currency": CURRENCY,
        })
        status_events.append({
            "event_id": format_status_event_id(ase_counter),
            "account_id": aid,
            "from_status": "",
            "to_status": "ACTIVE",
            "effective_ts": f"{c['onboarding_date']} 09:00:00",
            "reason": "OPENED",
        })
        ase_counter += 1

    # 2. Secondary accounts up to n_accounts target
    extra_needed = n_accounts - len(accounts)
    for i in range(extra_needed):
        c = customers[i % len(customers)]
        aid = format_account_id(c["customer_id"], 2)
        onboard_dt = datetime.datetime.strptime(c["onboarding_date"], DATE_FMT).date()
        open_dt = min(datetime.date(2026, 1, 1), onboard_dt + datetime.timedelta(days=rng.randint(30, 400)))
        bal = round(rng.uniform(10000.0, 80000.0), 2)
        accounts.append({
            "account_id": aid,
            "customer_id": c["customer_id"],
            "account_type": "SAVINGS",
            "open_date": open_dt.strftime(DATE_FMT),
            "close_date": "",
            "status": "ACTIVE",
            "starting_balance": f"{bal:.2f}",
            "overdraft_limit": "0.00",
            "currency": CURRENCY,
        })
        status_events.append({
            "event_id": format_status_event_id(ase_counter),
            "account_id": aid,
            "from_status": "",
            "to_status": "ACTIVE",
            "effective_ts": f"{open_dt.strftime(DATE_FMT)} 09:00:00",
            "reason": "OPENED",
        })
        ase_counter += 1

    return accounts, status_events

def generate_merchants(n_merchants: int, seed: int) -> List[Dict[str, Any]]:
    """Generate merchant directory with categories and risk levels."""
    rng = random.Random(f"{seed}:merchants")
    merchants = []
    cats = list(MERCHANT_CATEGORY_WEIGHTS.keys())
    weights = list(MERCHANT_CATEGORY_WEIGHTS.values())

    for i in range(1, n_merchants + 1):
        mid = format_merchant_id(i)
        cat = rng.choices(cats, weights=weights, k=1)[0]
        merchants.append({
            "merchant_id": mid,
            "merchant_name": f"Merchant {cat.title()} {i:04d}",
            "category": cat,
            "risk_level": MERCHANT_RISK_MAP.get(cat, "LOW"),
            "city": rng.choice(CITIES),
            "onboarding_date": "2024-01-15",
            "status": "ACTIVE",
        })
    return merchants

def generate_devices(customers: List[Dict[str, Any]], seed: int) -> List[Dict[str, Any]]:
    """Generate customer personal devices plus a shared fraud-pool."""
    rng = random.Random(f"{seed}:devices")
    devices = []
    dev_idx = 1

    # Personal devices: 1-2 per customer
    for c in customers:
        for _ in range(rng.choice([1, 1, 2])):
            did = format_device_id(dev_idx)
            dev_idx += 1
            dtype = rng.choice(DEVICE_TYPES)
            os_fam = "IOS" if dtype == "IOS" else ("ANDROID" if dtype == "ANDROID" else rng.choice(["WINDOWS", "MACOS"]))
            fp = hashlib.md5(f"{seed}:fp:{did}".encode()).hexdigest()[:16]
            devices.append({
                "device_id": did,
                "device_type": dtype,
                "os_family": os_fam,
                "fingerprint_hash": fp,
                "is_emulator": False,
                "status": "ACTIVE",
                "first_registered_date": c["onboarding_date"],
                "owner_customer_id": c["customer_id"],
            })

    # Fraud-pool / shared emulator devices
    pool_size = max(5, int(len(customers) * 0.05))
    for _ in range(pool_size):
        did = format_device_id(dev_idx)
        dev_idx += 1
        fp = hashlib.md5(f"{seed}:fp:{did}".encode()).hexdigest()[:16]
        devices.append({
            "device_id": did,
            "device_type": "ANDROID",
            "os_family": "ANDROID",
            "fingerprint_hash": fp,
            "is_emulator": rng.choice([True, False]),
            "status": "ACTIVE",
            "first_registered_date": "2025-01-01",
            "owner_customer_id": "",
        })
    return devices

def generate_analysts() -> List[Dict[str, Any]]:
    """Generate analyst personnel for triage and investigation."""
    analysts = []
    for aid, role in ANALYST_ROLES.items():
        analysts.append({
            "analyst_id": aid,
            "name": f"Analyst {aid}",
            "role": role,
            "status": "ACTIVE",
        })
    return analysts

def generate_master_data(cfg: Dict[str, Any], seed: int) -> Dict[str, Any]:
    """Orchestrate generation of all master tables."""
    customers = generate_customers(cfg["customers"], seed)
    accounts, status_events = generate_accounts(customers, cfg["accounts"], seed)
    merchants = generate_merchants(cfg["merchants"], seed)
    devices = generate_devices(customers, seed)
    analysts = generate_analysts()

    return {
        "customers": customers,
        "accounts": accounts,
        "account_status_events": status_events,
        "merchants": merchants,
        "devices": devices,
        "analysts": analysts,
    }

