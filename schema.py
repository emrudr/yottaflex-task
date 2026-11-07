"""Single source of truth for pipeline schemas, tables, fields, constraints, and doc generators."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

@dataclass
class FieldDef:
    name: str
    data_type: str
    required: bool
    allowed_values: Optional[List[str]] = None
    unit: Optional[str] = None
    unique: bool = False
    regex: Optional[str] = None
    description: str = ""

@dataclass
class ForeignKeyDef:
    column: str
    target_table: str
    target_column: str
    nullable: bool = False

@dataclass
class TableDef:
    name: str
    primary_key: List[str]
    fields: List[FieldDef]
    foreign_keys: List[ForeignKeyDef] = field(default_factory=list)
    description: str = ""

TABLE_DEFINITIONS: Dict[str, TableDef] = {
    "customers": TableDef(
        name="customers",
        primary_key=["customer_id"],
        fields=[
            FieldDef("customer_id", "VARCHAR(32)", True, unique=True, regex=r"^CUS-\d{6}$", description="Unique customer identifier"),
            FieldDef("full_name", "VARCHAR(128)", True, description="Customer full name (synthetic)"),
            FieldDef("date_of_birth", "DATE", True, description="Date of birth (1950-01-01 to 2005-12-31)"),
            FieldDef("email", "VARCHAR(128)", True, unique=True, regex=r"^cus-\d{6}@example\.test$", description="Unique synthetic email"),
            FieldDef("city", "VARCHAR(64)", True, description="Customer city"),
            FieldDef("segment", "VARCHAR(32)", True, allowed_values=["RETAIL", "SALARIED", "BUSINESS"], description="Customer segment"),
            FieldDef("kyc_status", "VARCHAR(32)", True, allowed_values=["VERIFIED", "EXPIRED", "PENDING"], description="KYC verification status"),
            FieldDef("kyc_risk_tier", "VARCHAR(32)", True, allowed_values=["LOW", "MEDIUM", "HIGH"], description="Assigned KYC risk tier"),
            FieldDef("kyc_verified_date", "DATE", False, description="Date KYC was verified; null iff PENDING"),
            FieldDef("kyc_expiry_date", "DATE", False, description="KYC expiration date; null iff PENDING"),
            FieldDef("onboarding_date", "DATE", True, description="Customer account relationship start date"),
        ],
        description="Master customer demographic and KYC records",
    ),
    "accounts": TableDef(
        name="accounts",
        primary_key=["account_id"],
        foreign_keys=[
            ForeignKeyDef("customer_id", "customers", "customer_id", nullable=False)
        ],
        fields=[
            FieldDef("account_id", "VARCHAR(64)", True, unique=True, regex=r"^ACC-CUS-\d{6}-\d{2}$", description="Unique account identifier"),
            FieldDef("customer_id", "VARCHAR(32)", True, description="Owning customer identifier"),
            FieldDef("account_type", "VARCHAR(32)", True, allowed_values=["SAVINGS", "CURRENT", "SALARY"], description="Account product type"),
            FieldDef("open_date", "DATE", True, description="Date account was opened"),
            FieldDef("close_date", "DATE", False, description="Date account was closed (null if open)"),
            FieldDef("status", "VARCHAR(32)", True, allowed_values=["ACTIVE", "DORMANT", "CLOSED"], description="Current account status (derived from lifecycle)"),
            FieldDef("starting_balance", "DECIMAL(15,2)", True, unit="INR", description="Balance at max(open_date, DATA_START)"),
            FieldDef("overdraft_limit", "DECIMAL(15,2)", True, unit="INR", description="Approved overdraft facility limit"),
            FieldDef("currency", "VARCHAR(3)", True, allowed_values=["INR"], description="Account currency"),
        ],
        description="Master customer financial accounts",
    ),
    "account_status_events": TableDef(
        name="account_status_events",
        primary_key=["event_id"],
        foreign_keys=[
            ForeignKeyDef("account_id", "accounts", "account_id", nullable=False)
        ],
        fields=[
            FieldDef("event_id", "VARCHAR(32)", True, unique=True, regex=r"^ASE-2026-\d{6}$", description="Unique lifecycle event identifier"),
            FieldDef("account_id", "VARCHAR(64)", True, description="Account identifier"),
            FieldDef("from_status", "VARCHAR(32)", False, allowed_values=["ACTIVE", "DORMANT", "CLOSED"], description="Previous status (null on opening)"),
            FieldDef("to_status", "VARCHAR(32)", True, allowed_values=["ACTIVE", "DORMANT", "CLOSED"], description="Target status after transition"),
            FieldDef("effective_ts", "TIMESTAMP", True, description="UTC timestamp of the transition"),
            FieldDef("reason", "VARCHAR(64)", True, allowed_values=["OPENED", "INACTIVITY_180D", "REACTIVATED_BY_ACTIVITY", "CLOSED_BY_CUSTOMER"], description="Business reason for lifecycle transition"),
        ],
        description="Append-only lifecycle event journal for accounts",
    ),
    "merchants": TableDef(
        name="merchants",
        primary_key=["merchant_id"],
        fields=[
            FieldDef("merchant_id", "VARCHAR(32)", True, unique=True, regex=r"^MER-\d{6}$", description="Unique merchant identifier"),
            FieldDef("merchant_name", "VARCHAR(128)", True, description="Trading name of merchant"),
            FieldDef("category", "VARCHAR(32)", True, allowed_values=[
                "GROCERY", "FUEL", "ELECTRONICS", "TRAVEL", "DINING", "UTILITIES",
                "ENTERTAINMENT", "HEALTHCARE", "ECOMMERCE", "GAMBLING", "CRYPTO_EXCHANGE", "JEWELRY"
            ], description="Merchant industry code"),
            FieldDef("risk_level", "VARCHAR(32)", True, allowed_values=["LOW", "MEDIUM", "HIGH"], description="Derived category risk tier"),
            FieldDef("city", "VARCHAR(64)", True, description="Merchant physical or registered city"),
            FieldDef("onboarding_date", "DATE", True, description="Merchant onboarding date"),
            FieldDef("status", "VARCHAR(32)", True, allowed_values=["ACTIVE", "INACTIVE"], description="Merchant processing status"),
        ],
        description="Registered merchants and payees",
    ),
    "devices": TableDef(
        name="devices",
        primary_key=["device_id"],
        foreign_keys=[
            ForeignKeyDef("owner_customer_id", "customers", "customer_id", nullable=True)
        ],
        fields=[
            FieldDef("device_id", "VARCHAR(32)", True, unique=True, regex=r"^DEV-\d{6}$", description="Unique hardware device identifier"),
            FieldDef("device_type", "VARCHAR(32)", True, allowed_values=["ANDROID", "IOS", "WEB_BROWSER"], description="Device hardware type"),
            FieldDef("os_family", "VARCHAR(32)", True, allowed_values=["ANDROID", "IOS", "WINDOWS", "MACOS", "LINUX"], description="Operating system family"),
            FieldDef("fingerprint_hash", "VARCHAR(64)", True, description="Deterministic 16-hex fingerprint hash"),
            FieldDef("is_emulator", "BOOLEAN", True, description="Flag indicating emulated/virtualized environment"),
            FieldDef("status", "VARCHAR(32)", True, allowed_values=["ACTIVE"], description="Device lifecycle state"),
            FieldDef("first_registered_date", "DATE", True, description="Date first registered in the banking channel"),
            FieldDef("owner_customer_id", "VARCHAR(32)", False, description="Owning customer (null for shared/fraud-pool devices)"),
        ],
        description="Hardware devices and browser instances",
    ),
    "account_devices": TableDef(
        name="account_devices",
        primary_key=["account_id", "device_id"],
        foreign_keys=[
            ForeignKeyDef("account_id", "accounts", "account_id", nullable=False),
            ForeignKeyDef("device_id", "devices", "device_id", nullable=False),
        ],
        fields=[
            FieldDef("account_id", "VARCHAR(64)", True, description="Account identifier"),
            FieldDef("device_id", "VARCHAR(32)", True, description="Device identifier"),
            FieldDef("first_seen_ts", "TIMESTAMP", True, description="First transaction timestamp on this device"),
            FieldDef("last_seen_ts", "TIMESTAMP", True, description="Most recent transaction timestamp on this device"),
            FieldDef("txn_count", "INTEGER", True, description="Total transactions executed using this device"),
            FieldDef("link_status", "VARCHAR(32)", True, allowed_values=["ACTIVE", "INACTIVE"], description="ACTIVE if last seen within 90 days of DATA_END"),
        ],
        description="Bridge table recording account-to-device interaction history",
    ),
    "transactions": TableDef(
        name="transactions",
        primary_key=["txn_id"],
        foreign_keys=[
            ForeignKeyDef("account_id", "accounts", "account_id", nullable=False),
            ForeignKeyDef("merchant_id", "merchants", "merchant_id", nullable=True),
            ForeignKeyDef("device_id", "devices", "device_id", nullable=True),
            ForeignKeyDef("counterparty_account_id", "accounts", "account_id", nullable=True),
            ForeignKeyDef("transfer_id", "transfer_links", "transfer_id", nullable=True),
        ],
        fields=[
            FieldDef("txn_id", "VARCHAR(32)", True, unique=True, regex=r"^TXN-2026-\d{8}$", description="Unique transaction reference"),
            FieldDef("account_id", "VARCHAR(64)", True, description="Posting account identifier"),
            FieldDef("txn_ts", "TIMESTAMP", True, description="UTC transaction timestamp"),
            FieldDef("txn_type", "VARCHAR(32)", True, allowed_values=[
                "POS_PURCHASE", "ATM_WITHDRAWAL", "UPI_PAYMENT", "BILL_PAYMENT",
                "NEFT_TRANSFER_OUT", "TRANSFER_IN", "SALARY_CREDIT", "CASH_DEPOSIT",
                "REFUND", "CLOSURE_PAYOUT"
            ], description="Transaction classification"),
            FieldDef("direction", "VARCHAR(8)", True, allowed_values=["DEBIT", "CREDIT"], description="Cashflow direction"),
            FieldDef("amount", "DECIMAL(15,2)", True, unit="INR", description="Absolute transaction value (> 0)"),
            FieldDef("balance_before", "DECIMAL(15,2)", True, unit="INR", description="Ledger balance immediately prior to posting"),
            FieldDef("balance_after", "DECIMAL(15,2)", True, unit="INR", description="Ledger balance immediately after posting"),
            FieldDef("channel", "VARCHAR(32)", True, allowed_values=["MOBILE_APP", "WEB", "POS", "ATM", "BRANCH", "UPI"], description="Execution channel"),
            FieldDef("merchant_id", "VARCHAR(32)", False, description="Referenced merchant identifier"),
            FieldDef("device_id", "VARCHAR(32)", False, description="Referenced hardware device identifier"),
            FieldDef("counterparty_account_id", "VARCHAR(64)", False, description="Referenced counterparty account (internal transfers)"),
            FieldDef("transfer_id", "VARCHAR(32)", False, description="Referenced bilateral transfer link"),
        ],
        description="Immutable financial ledger transactions",
    ),
    "transfer_links": TableDef(
        name="transfer_links",
        primary_key=["transfer_id"],
        foreign_keys=[
            ForeignKeyDef("source_account_id", "accounts", "account_id", nullable=False),
            ForeignKeyDef("dest_account_id", "accounts", "account_id", nullable=False),
            ForeignKeyDef("debit_txn_id", "transactions", "txn_id", nullable=False),
            ForeignKeyDef("credit_txn_id", "transactions", "txn_id", nullable=False),
        ],
        fields=[
            FieldDef("transfer_id", "VARCHAR(32)", True, unique=True, regex=r"^TRF-2026-\d{6}$", description="Bilateral transfer link identifier"),
            FieldDef("source_account_id", "VARCHAR(64)", True, description="Originating source account"),
            FieldDef("dest_account_id", "VARCHAR(64)", True, description="Destination target account"),
            FieldDef("debit_txn_id", "VARCHAR(32)", True, unique=True, description="Debit ledger transaction reference"),
            FieldDef("credit_txn_id", "VARCHAR(32)", True, unique=True, description="Credit ledger transaction reference"),
            FieldDef("amount", "DECIMAL(15,2)", True, unit="INR", description="Agreed transfer amount"),
            FieldDef("initiated_ts", "TIMESTAMP", True, description="Timestamp debit leg initiated"),
            FieldDef("settled_ts", "TIMESTAMP", True, description="Timestamp credit leg settled"),
            FieldDef("status", "VARCHAR(32)", True, allowed_values=["SETTLED"], description="Settlement status"),
        ],
        description="Bilateral linkages connecting internal transfer debit and credit legs",
    ),
    "risk_rules": TableDef(
        name="risk_rules",
        primary_key=["rule_id"],
        fields=[
            FieldDef("rule_id", "VARCHAR(16)", True, unique=True, regex=r"^[RA]\d{2}$", description="Rule code (R01..R05 detection, A01..A04 adjustments)"),
            FieldDef("rule_name", "VARCHAR(64)", True, description="Canonical rule name"),
            FieldDef("rule_type", "VARCHAR(32)", True, allowed_values=["DETECTION", "ADJUSTMENT"], description="Rule functional category"),
            FieldDef("description", "VARCHAR(256)", True, description="Detailed rule description and trigger condition"),
            FieldDef("base_points", "INTEGER", True, description="Base score points contributed (negative for adjustments)"),
            FieldDef("parameters_json", "TEXT", True, description="JSON configuration defining operational thresholds"),
            FieldDef("effective_from", "DATE", True, description="Rule activation date"),
            FieldDef("effective_to", "DATE", False, description="Rule expiration date (null if active)"),
            FieldDef("status", "VARCHAR(32)", True, allowed_values=["ACTIVE", "INACTIVE"], description="Rule operational status"),
        ],
        description="Configuration and threshold definitions for detection rules and score adjustments",
    ),
    "analysts": TableDef(
        name="analysts",
        primary_key=["analyst_id"],
        fields=[
            FieldDef("analyst_id", "VARCHAR(16)", True, unique=True, regex=r"^ANL-\d{3}$", description="Unique analyst personnel identifier"),
            FieldDef("name", "VARCHAR(128)", True, description="Analyst full name"),
            FieldDef("role", "VARCHAR(32)", True, allowed_values=["OPS_ANALYST", "RISK_REVIEWER", "SYSTEM_ADMIN"], description="Analyst operational role"),
            FieldDef("status", "VARCHAR(32)", True, allowed_values=["ACTIVE", "INACTIVE"], description="Analyst access status"),
        ],
        description="Operational and compliance personnel responsible for triage and disposition",
    ),
    "alerts": TableDef(
        name="alerts",
        primary_key=["alert_id"],
        foreign_keys=[
            ForeignKeyDef("rule_id", "risk_rules", "rule_id", nullable=False),
            ForeignKeyDef("trigger_txn_id", "transactions", "txn_id", nullable=True),
            ForeignKeyDef("account_id", "accounts", "account_id", nullable=False),
            ForeignKeyDef("customer_id", "customers", "customer_id", nullable=False),
            ForeignKeyDef("case_id", "cases", "case_id", nullable=False),
        ],
        fields=[
            FieldDef("alert_id", "VARCHAR(32)", True, unique=True, regex=r"^ALT-2026-\d{6}$", description="Unique risk alert reference"),
            FieldDef("rule_id", "VARCHAR(16)", True, description="Primary rule triggering this alert"),
            FieldDef("trigger_txn_id", "VARCHAR(32)", False, description="Transaction triggering the alert (null for injected headless anomaly)"),
            FieldDef("account_id", "VARCHAR(64)", True, description="Subject account"),
            FieldDef("customer_id", "VARCHAR(32)", True, description="Subject customer"),
            FieldDef("created_ts", "TIMESTAMP", True, description="UTC alert timestamp (trigger txn + 5 minutes)"),
            FieldDef("risk_score", "INTEGER", True, description="Calculated risk score clamped to [0, 100]"),
            FieldDef("severity", "VARCHAR(32)", True, allowed_values=["CRITICAL", "HIGH", "MEDIUM", "LOW"], description="Severity derived from risk_score"),
            FieldDef("priority_rank", "INTEGER", True, description="Contiguous 1..N global priority ranking"),
            FieldDef("status", "VARCHAR(32)", True, allowed_values=["OPEN", "CLOSED_TRUE_POSITIVE", "CLOSED_FALSE_POSITIVE"], description="Derived alert lifecycle status"),
            FieldDef("case_id", "VARCHAR(32)", True, description="Associated investigation case identifier"),
            FieldDef("explanation", "TEXT", True, description="Human-readable explainability narrative with parameter values"),
        ],
        description="Synthesized risk alerts prioritized for review",
    ),
    "alert_evidence": TableDef(
        name="alert_evidence",
        primary_key=["alert_id", "txn_id"],
        foreign_keys=[
            ForeignKeyDef("alert_id", "alerts", "alert_id", nullable=False),
            ForeignKeyDef("txn_id", "transactions", "txn_id", nullable=False),
        ],
        fields=[
            FieldDef("alert_id", "VARCHAR(32)", True, description="Alert identifier"),
            FieldDef("txn_id", "VARCHAR(32)", True, description="Associated transaction evidence identifier"),
            FieldDef("role", "VARCHAR(32)", True, allowed_values=["TRIGGER", "SUPPORTING"], description="Evidentiary role of transaction"),
        ],
        description="N:M bridge connecting risk alerts to relevant ledger transactions",
    ),
    "alert_score_components": TableDef(
        name="alert_score_components",
        primary_key=["alert_id", "seq"],
        foreign_keys=[
            ForeignKeyDef("alert_id", "alerts", "alert_id", nullable=False),
            ForeignKeyDef("rule_id", "risk_rules", "rule_id", nullable=True),
        ],
        fields=[
            FieldDef("alert_id", "VARCHAR(32)", True, description="Alert identifier"),
            FieldDef("seq", "INTEGER", True, description="Evaluation sequence order for score derivation"),
            FieldDef("component_code", "VARCHAR(64)", True, description="Score component identifier (base, bonus, adjustment, tier)"),
            FieldDef("rule_id", "VARCHAR(16)", False, description="Contributing rule identifier (if rule-based)"),
            FieldDef("points", "INTEGER", True, description="Signed score points applied"),
            FieldDef("detail", "TEXT", True, description="Contextual data supporting the score increment/decrement"),
        ],
        description="Explainability breakdown detailing every additive/subtractive score element",
    ),
    "cases": TableDef(
        name="cases",
        primary_key=["case_id"],
        foreign_keys=[
            ForeignKeyDef("primary_account_id", "accounts", "account_id", nullable=False),
            ForeignKeyDef("assigned_analyst_id", "analysts", "analyst_id", nullable=True),
        ],
        fields=[
            FieldDef("case_id", "VARCHAR(32)", True, unique=True, regex=r"^CASE-2026-\d{6}$", description="Investigation case identifier"),
            FieldDef("primary_account_id", "VARCHAR(64)", True, description="Account associated with highest scoring constituent alert"),
            FieldDef("opened_ts", "TIMESTAMP", True, description="Case creation timestamp (earliest alert created_ts)"),
            FieldDef("closed_ts", "TIMESTAMP", False, description="Case closure timestamp (null if active)"),
            FieldDef("alert_count", "INTEGER", True, description="Number of alerts grouped into this case"),
            FieldDef("case_score", "INTEGER", True, description="Composite case risk score clamped to [0, 100]"),
            FieldDef("priority", "VARCHAR(8)", True, allowed_values=["P1", "P2", "P3", "P4"], description="Operational priority band"),
            FieldDef("status", "VARCHAR(32)", True, allowed_values=["OPEN", "ASSIGNED", "UNDER_REVIEW", "ESCALATED", "CLOSED"], description="Current case investigation status"),
            FieldDef("assigned_analyst_id", "VARCHAR(16)", False, description="Currently assigned analyst identifier"),
            FieldDef("final_disposition", "VARCHAR(32)", False, allowed_values=["TRUE_POSITIVE", "FALSE_POSITIVE"], description="Final case outcome (null if unclosed)"),
        ],
        description="Investigation cases aggregating correlated alerts across time and accounts",
    ),
    "analyst_actions": TableDef(
        name="analyst_actions",
        primary_key=["action_id"],
        foreign_keys=[
            ForeignKeyDef("case_id", "cases", "case_id", nullable=False),
            ForeignKeyDef("alert_id", "alerts", "alert_id", nullable=True),
            ForeignKeyDef("analyst_id", "analysts", "analyst_id", nullable=False),
        ],
        fields=[
            FieldDef("action_id", "VARCHAR(32)", True, unique=True, regex=r"^ACT-2026-\d{6}$", description="Workflow action event identifier"),
            FieldDef("case_id", "VARCHAR(32)", True, description="Subject case identifier"),
            FieldDef("alert_id", "VARCHAR(32)", False, description="Referenced alert identifier (null for case-level actions)"),
            FieldDef("analyst_id", "VARCHAR(16)", True, description="Actor analyst identifier"),
            FieldDef("action_type", "VARCHAR(32)", True, allowed_values=["ASSIGN", "REVIEW_START", "ESCALATE", "DISPOSITION", "CLOSE"], description="Action category"),
            FieldDef("disposition", "VARCHAR(32)", False, allowed_values=["TRUE_POSITIVE", "FALSE_POSITIVE", "NEEDS_MORE_INFO"], description="Disposition finding (for DISPOSITION actions)"),
            FieldDef("action_ts", "TIMESTAMP", True, description="Timestamp action was executed"),
            FieldDef("note", "TEXT", True, description="Structured audit log rationale"),
        ],
        description="Append-only audit trail of analyst workflow operations and findings",
    ),
}

DEFAULT_RULES_SEED_DATA: List[Dict[str, Any]] = [
    {
        "rule_id": "R01",
        "rule_name": "VELOCITY_SPIKE",
        "rule_type": "DETECTION",
        "description": "High volume of debit transactions within a 60-minute window",
        "base_points": 60,
        "parameters_json": json.dumps({
            "window_minutes": 60,
            "min_count": 6,
            "bonus_count_threshold": 10,
            "bonus_count_points": 15,
            "bonus_amount_threshold": 50000.0,
            "bonus_amount_points": 15
        }, sort_keys=True),
        "effective_from": "2026-01-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
    {
        "rule_id": "R02",
        "rule_name": "NEW_DEVICE_ACTIVITY",
        "rule_type": "DETECTION",
        "description": "Significant debit activity on a newly observed device for an established account",
        "base_points": 55,
        "parameters_json": json.dumps({
            "min_amount": 15000.0,
            "min_prior_account_txns": 5,
            "bonus_large_amount": 50000.0,
            "bonus_large_points": 15,
            "bonus_emulator_or_shared_accounts": 3,
            "bonus_emulator_points": 15
        }, sort_keys=True),
        "effective_from": "2026-01-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
    {
        "rule_id": "R03",
        "rule_name": "CIRCULAR_TRANSFER",
        "rule_type": "DETECTION",
        "description": "Circular transfer path where funds return to origin account within 72 hours",
        "base_points": 60,
        "parameters_json": json.dumps({
            "min_transfer_amount": 5000.0,
            "max_window_hours": 72,
            "min_hops": 2,
            "max_hops": 5,
            "bonus_distinct_customers": 3,
            "bonus_distinct_customers_points": 20,
            "bonus_retention_ratio": 0.90,
            "bonus_retention_points": 15
        }, sort_keys=True),
        "effective_from": "2026-01-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
    {
        "rule_id": "R04",
        "rule_name": "DORMANT_REACTIVATION",
        "rule_type": "DETECTION",
        "description": "Substantial transaction following a period of inactivity exceeding 180 days",
        "base_points": 55,
        "parameters_json": json.dumps({
            "inactivity_gap_days": 180,
            "min_amount": 10000.0,
            "bonus_debit_drain_ratio": 0.80,
            "bonus_debit_drain_points": 25,
            "bonus_new_device_points": 15
        }, sort_keys=True),
        "effective_from": "2026-01-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
    {
        "rule_id": "R05",
        "rule_name": "AMOUNT_OUTLIER",
        "rule_type": "DETECTION",
        "description": "Debit transaction significantly exceeding historical baseline median",
        "base_points": 45,
        "parameters_json": json.dumps({
            "min_amount": 25000.0,
            "min_prior_debits": 5,
            "outlier_multiplier": 8.0,
            "bonus_extreme_multiplier": 15.0,
            "bonus_extreme_points": 15,
            "bonus_high_risk_merchant_points": 10
        }, sort_keys=True),
        "effective_from": "2026-01-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
    {
        "rule_id": "A01",
        "rule_name": "SAME_OWNER_TRANSFER",
        "rule_type": "ADJUSTMENT",
        "description": "All accounts in circular transfer path are owned by the same customer",
        "base_points": -40,
        "parameters_json": json.dumps({
            "match_owner_scope": "ALL_ACCOUNTS"
        }, sort_keys=True),
        "effective_from": "2026-01-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
    {
        "rule_id": "A02",
        "rule_name": "TRUSTED_CUSTOMER",
        "rule_type": "ADJUSTMENT",
        "description": "Customer has verified KYC, low risk tier, and tenure of at least 3 years",
        "base_points": -15,
        "parameters_json": json.dumps({
            "min_tenure_years": 3,
            "required_kyc_status": "VERIFIED",
            "required_kyc_tier": "LOW"
        }, sort_keys=True),
        "effective_from": "2026-01-01",
        "effective_to": None,
        "status": "ACTIVE",
    },
]

def generate_data_dictionary_md() -> str:
    """Generate Markdown documentation for all tables and fields from the schema definition."""
    lines: List[str] = [
        "# Data Dictionary",
        "",
        "This data dictionary is automatically generated from `schema.py`, which serves as the single source of truth for all table structures, field definitions, data types, constraints, and relationships.",
        "",
    ]
    for table_name, tdef in sorted(TABLE_DEFINITIONS.items()):
        lines.append(f"## Table: `{tdef.name}`")
        lines.append(f"**Description:** {tdef.description}")
        lines.append(f"**Primary Key:** `{', '.join(tdef.primary_key)}`")
        if tdef.foreign_keys:
            fk_strs = [f"`{fk.column}` → `{fk.target_table}.{fk.target_column}`" for fk in tdef.foreign_keys]
            lines.append(f"**Foreign Keys:** {'; '.join(fk_strs)}")
        lines.append("")
        lines.append("| Field Name | Type | Required | Allowed Values / Format | Description |")
        lines.append("|---|---|---|---|---|")
        for f in tdef.fields:
            req_str = "Yes" if f.required else "No"
            allowed_str = ", ".join(f.allowed_values) if f.allowed_values else (f"`{f.regex}`" if f.regex else "-")
            lines.append(f"| `{f.name}` | {f.data_type} | {req_str} | {allowed_str} | {f.description} |")
        lines.append("")
    return "\n".join(lines)

def generate_rules_md(rules: List[Dict[str, Any]]) -> str:
    """Generate Markdown documentation for risk rules directly from rule parameter definitions."""
    lines: List[str] = [
        "# Risk Rules Catalog & Thresholds",
        "",
        "This document is auto-generated from `risk_rules.csv`. All rules are config-driven and evaluate strictly over observable dataset features without access to ground truth.",
        "",
        "| Rule ID | Rule Name | Type | Base Points | Description | Parameters |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(rules, key=lambda x: str(x["rule_id"])):
        params = json.loads(r["parameters_json"]) if isinstance(r["parameters_json"], str) else r["parameters_json"]
        param_str = "<br>".join(f"• `{k}`: {v}" for k, v in sorted(params.items()))
        lines.append(f"| `{r['rule_id']}` | **{r['rule_name']}** | {r['rule_type']} | {r['base_points']} | {r['description']} | {param_str} |")
    lines.append("")
    return "\n".join(lines)
