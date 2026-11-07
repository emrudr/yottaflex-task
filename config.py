"""Configuration, presets, constants, and global conventions for the pipeline."""

from __future__ import annotations

import math
from typing import Any, Dict, List

# Global Seed and Time Window
SEED: int = 20261022
DATA_START: str = "2026-01-01 00:00:00"
DATA_END: str = "2026-10-31 23:59:59"
CURRENCY: str = "INR"
DATE_FMT: str = "%Y-%m-%d"
DT_FMT: str = "%Y-%m-%d %H:%M:%S"

# ID Formatting Helpers
def format_customer_id(idx: int) -> str:
    return f"CUS-{idx:06d}"

def format_account_id(customer_id: str, sub_id: int) -> str:
    return f"ACC-{customer_id}-{sub_id:02d}"

def format_merchant_id(idx: int) -> str:
    return f"MER-{idx:06d}"

def format_device_id(idx: int) -> str:
    return f"DEV-{idx:06d}"

def format_txn_id(idx: int) -> str:
    return f"TXN-2026-{idx:08d}"

def format_transfer_id(idx: int) -> str:
    return f"TRF-2026-{idx:06d}"

def format_alert_id(idx: int) -> str:
    return f"ALT-2026-{idx:06d}"

def format_case_id(idx: int) -> str:
    return f"CASE-2026-{idx:06d}"

def format_action_id(idx: int) -> str:
    return f"ACT-2026-{idx:06d}"

def format_status_event_id(idx: int) -> str:
    return f"ASE-2026-{idx:06d}"

def format_analyst_id(idx: int) -> str:
    return f"ANL-{idx:03d}"

def format_scenario_id(idx: int) -> str:
    return f"SCN-{idx:06d}"

# Scale Presets
SCALE_PRESETS: Dict[str, Dict[str, int]] = {
    "starter": {
        "customers": 250,
        "accounts": 350,
        "transactions": 5000,
        "alerts_target": 50,
        "merchants": 30,
        "analysts": 12,
    },
    "full": {
        "customers": 5000,
        "accounts": 7000,
        "transactions": 100000,
        "alerts_target": 1000,
        "merchants": 600,
        "analysts": 12,
    },
}

FULL_SCENARIO_COUNTS: Dict[str, int] = {
    "TRUE_VELOCITY": 130,
    "TRUE_NEW_DEVICE": 130,
    "TRUE_CIRCULAR": 40,
    "TRUE_DORMANT": 85,
    "TRUE_OUTLIER": 90,
    "FP_VELOCITY": 75,
    "FP_NEW_DEVICE": 80,
    "FP_DORMANT": 38,
    "FP_CIRCULAR": 30,
    "INJ_CLOSED_ACCOUNT_TXN": 10,
    "INJ_NEGATIVE_BALANCE_NO_OD": 10,
    "INJ_TRANSFER_LEG_MISMATCH": 10,
    "INJ_ALERT_NO_TRIGGER": 5,
    "INJ_DISPOSITION_BEFORE_ALERT": 5,
}

def round_half_up(n: float) -> int:
    return int(math.floor(n + 0.5))

def get_scenario_counts(scale_factor: float) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for scn_type, full_count in FULL_SCENARIO_COUNTS.items():
        scaled = round_half_up(full_count * scale_factor)
        counts[scn_type] = max(2, scaled)
    return counts

def get_scale_config(preset: str = "starter") -> Dict[str, Any]:
    if preset not in SCALE_PRESETS:
        raise ValueError(f"Unknown scale preset: {preset}. Choose 'starter' or 'full'.")
    cfg = dict(SCALE_PRESETS[preset])
    scale_factor = cfg["customers"] / 5000.0
    cfg["scale_factor"] = scale_factor
    cfg["scenario_counts"] = get_scenario_counts(scale_factor)
    return cfg

# Domain Data & Lists
FIRST_NAMES: List[str] = [
    "Aarav", "Aditi", "Ajay", "Amit", "Ananya", "Anita", "Ankit", "Arjun",
    "Bhavna", "Chetan", "Deepak", "Divya", "Gaurav", "Geeta", "Harish", "Isha",
    "Kavita", "Kiran", "Kunal", "Madhav", "Manish", "Meera", "Neha", "Nikhil",
    "Pooja", "Pranav", "Priya", "Rahul", "Rajesh", "Ritu", "Rohan", "Sanjay",
    "Shreya", "Siddharth", "Sneha", "Sunil", "Suresh", "Tanvi", "Varun", "Vikas"
]

LAST_NAMES: List[str] = [
    "Agarwal", "Bose", "Chawla", "Deshmukh", "Dutta", "Gupta", "Iyer", "Jain",
    "Joshi", "Kapoor", "Khan", "Kumar", "Mehta", "Mishra", "Mukherjee", "Nair",
    "Patel", "Pillai", "Prasad", "Rao", "Reddy", "Roy", "Sahay", "Saxena",
    "Sen", "Shah", "Sharma", "Singh", "Soni", "Srivastava", "Talwar", "Tandon",
    "Trivedi", "Varma", "Verma", "Vyas", "Wadhwa", "Yadav", "Bhatia", "Chopra"
]

CITIES: List[str] = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Ahmedabad",
    "Chennai", "Kolkata", "Surat", "Pune", "Jaipur",
    "Lucknow", "Kanpur", "Nagpur", "Indore", "Bhopal"
]

MERCHANT_CATEGORIES: List[str] = [
    "GROCERY", "FUEL", "ELECTRONICS", "TRAVEL", "DINING", "UTILITIES",
    "ENTERTAINMENT", "HEALTHCARE", "ECOMMERCE", "GAMBLING", "CRYPTO_EXCHANGE", "JEWELRY"
]

MERCHANT_CATEGORY_WEIGHTS: Dict[str, int] = {
    "GROCERY": 18,
    "FUEL": 10,
    "DINING": 14,
    "UTILITIES": 12,
    "ECOMMERCE": 14,
    "ENTERTAINMENT": 6,
    "HEALTHCARE": 6,
    "TRAVEL": 6,
    "ELECTRONICS": 6,
    "JEWELRY": 3,
    "GAMBLING": 3,
    "CRYPTO_EXCHANGE": 2,
}

MERCHANT_RISK_MAP: Dict[str, str] = {
    "GAMBLING": "HIGH",
    "CRYPTO_EXCHANGE": "HIGH",
    "JEWELRY": "MEDIUM",
    "ELECTRONICS": "MEDIUM",
    "TRAVEL": "MEDIUM",
    "GROCERY": "LOW",
    "FUEL": "LOW",
    "DINING": "LOW",
    "UTILITIES": "LOW",
    "ENTERTAINMENT": "LOW",
    "HEALTHCARE": "LOW",
    "ECOMMERCE": "LOW",
}

CUSTOMER_SEGMENTS: List[str] = ["RETAIL", "SALARIED", "BUSINESS"]
CUSTOMER_SEGMENT_WEIGHTS: List[int] = [55, 35, 10]

KYC_STATUSES: List[str] = ["VERIFIED", "EXPIRED", "PENDING"]
KYC_STATUS_WEIGHTS: List[int] = [94, 4, 2]

KYC_RISK_TIERS: List[str] = ["LOW", "MEDIUM", "HIGH"]
KYC_RISK_TIER_WEIGHTS: List[int] = [70, 22, 8]

ACCOUNT_TYPES: List[str] = ["SAVINGS", "CURRENT", "SALARY"]
ACCOUNT_STATUSES: List[str] = ["ACTIVE", "DORMANT", "CLOSED"]
STATUS_REASONS: List[str] = ["OPENED", "INACTIVITY_180D", "REACTIVATED_BY_ACTIVITY", "CLOSED_BY_CUSTOMER"]

DEVICE_TYPES: List[str] = ["ANDROID", "IOS", "WEB_BROWSER"]
OS_FAMILIES: List[str] = ["ANDROID", "IOS", "WINDOWS", "MACOS", "LINUX"]

TRANSACTION_TYPES: List[str] = [
    "POS_PURCHASE", "ATM_WITHDRAWAL", "UPI_PAYMENT", "BILL_PAYMENT",
    "NEFT_TRANSFER_OUT", "TRANSFER_IN", "SALARY_CREDIT", "CASH_DEPOSIT",
    "REFUND", "CLOSURE_PAYOUT"
]
TRANSACTION_DIRECTIONS: List[str] = ["DEBIT", "CREDIT"]
CHANNELS: List[str] = ["MOBILE_APP", "WEB", "POS", "ATM", "BRANCH", "UPI"]

SEVERITY_LEVELS: List[str] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
CASE_PRIORITIES: List[str] = ["P1", "P2", "P3", "P4"]
CASE_STATUSES: List[str] = ["OPEN", "ASSIGNED", "UNDER_REVIEW", "ESCALATED", "CLOSED"]
ALERT_STATUSES: List[str] = ["OPEN", "CLOSED_TRUE_POSITIVE", "CLOSED_FALSE_POSITIVE"]
ANALYST_ACTIONS: List[str] = ["ASSIGN", "REVIEW_START", "ESCALATE", "DISPOSITION", "CLOSE"]
DISPOSITIONS: List[str] = ["TRUE_POSITIVE", "FALSE_POSITIVE", "NEEDS_MORE_INFO"]

ANALYST_ROLES: Dict[str, str] = {
    **{format_analyst_id(i): "OPS_ANALYST" for i in range(1, 9)},
    **{format_analyst_id(i): "RISK_REVIEWER" for i in range(9, 12)},
    format_analyst_id(12): "SYSTEM_ADMIN",
}

