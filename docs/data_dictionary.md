# Data Dictionary

This data dictionary is automatically generated from `schema.py`, which serves as the single source of truth for all table structures, field definitions, data types, constraints, and relationships.

## Table: `account_devices`
**Description:** Bridge table recording account-to-device interaction history
**Primary Key:** `account_id, device_id`
**Foreign Keys:** `account_id` → `accounts.account_id`; `device_id` → `devices.device_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `account_id` | VARCHAR(64) | Yes | - | Account identifier |
| `device_id` | VARCHAR(32) | Yes | - | Device identifier |
| `first_seen_ts` | TIMESTAMP | Yes | - | First transaction timestamp on this device |
| `last_seen_ts` | TIMESTAMP | Yes | - | Most recent transaction timestamp on this device |
| `txn_count` | INTEGER | Yes | - | Total transactions executed using this device |
| `link_status` | VARCHAR(32) | Yes | ACTIVE, INACTIVE | ACTIVE if last seen within 90 days of DATA_END |

## Table: `account_status_events`
**Description:** Append-only lifecycle event journal for accounts
**Primary Key:** `event_id`
**Foreign Keys:** `account_id` → `accounts.account_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `event_id` | VARCHAR(32) | Yes | `^ASE-2026-\d{6}$` | Unique lifecycle event identifier |
| `account_id` | VARCHAR(64) | Yes | - | Account identifier |
| `from_status` | VARCHAR(32) | No | ACTIVE, DORMANT, CLOSED | Previous status (null on opening) |
| `to_status` | VARCHAR(32) | Yes | ACTIVE, DORMANT, CLOSED | Target status after transition |
| `effective_ts` | TIMESTAMP | Yes | - | UTC timestamp of the transition |
| `reason` | VARCHAR(64) | Yes | OPENED, INACTIVITY_180D, REACTIVATED_BY_ACTIVITY, CLOSED_BY_CUSTOMER | Business reason for lifecycle transition |

## Table: `accounts`
**Description:** Master customer financial accounts
**Primary Key:** `account_id`
**Foreign Keys:** `customer_id` → `customers.customer_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `account_id` | VARCHAR(64) | Yes | `^ACC-CUS-\d{6}-\d{2}$` | Unique account identifier |
| `customer_id` | VARCHAR(32) | Yes | - | Owning customer identifier |
| `account_type` | VARCHAR(32) | Yes | SAVINGS, CURRENT, SALARY | Account product type |
| `open_date` | DATE | Yes | - | Date account was opened |
| `close_date` | DATE | No | - | Date account was closed (null if open) |
| `status` | VARCHAR(32) | Yes | ACTIVE, DORMANT, CLOSED | Current account status (derived from lifecycle) |
| `starting_balance` | DECIMAL(15,2) | Yes | - | Balance at max(open_date, DATA_START) |
| `overdraft_limit` | DECIMAL(15,2) | Yes | - | Approved overdraft facility limit |
| `currency` | VARCHAR(3) | Yes | INR | Account currency |

## Table: `alert_evidence`
**Description:** N:M bridge connecting risk alerts to relevant ledger transactions
**Primary Key:** `alert_id, txn_id`
**Foreign Keys:** `alert_id` → `alerts.alert_id`; `txn_id` → `transactions.txn_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `alert_id` | VARCHAR(32) | Yes | - | Alert identifier |
| `txn_id` | VARCHAR(32) | Yes | - | Associated transaction evidence identifier |
| `role` | VARCHAR(32) | Yes | TRIGGER, SUPPORTING | Evidentiary role of transaction |

## Table: `alert_score_components`
**Description:** Explainability breakdown detailing every additive/subtractive score element
**Primary Key:** `alert_id, seq`
**Foreign Keys:** `alert_id` → `alerts.alert_id`; `rule_id` → `risk_rules.rule_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `alert_id` | VARCHAR(32) | Yes | - | Alert identifier |
| `seq` | INTEGER | Yes | - | Evaluation sequence order for score derivation |
| `component_code` | VARCHAR(64) | Yes | - | Score component identifier (base, bonus, adjustment, tier) |
| `rule_id` | VARCHAR(16) | No | - | Contributing rule identifier (if rule-based) |
| `points` | INTEGER | Yes | - | Signed score points applied |
| `detail` | TEXT | Yes | - | Contextual data supporting the score increment/decrement |

## Table: `alerts`
**Description:** Synthesized risk alerts prioritized for review
**Primary Key:** `alert_id`
**Foreign Keys:** `rule_id` → `risk_rules.rule_id`; `trigger_txn_id` → `transactions.txn_id`; `account_id` → `accounts.account_id`; `customer_id` → `customers.customer_id`; `case_id` → `cases.case_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `alert_id` | VARCHAR(32) | Yes | `^ALT-2026-\d{6}$` | Unique risk alert reference |
| `rule_id` | VARCHAR(16) | Yes | - | Primary rule triggering this alert |
| `trigger_txn_id` | VARCHAR(32) | No | - | Transaction triggering the alert (null for injected headless anomaly) |
| `account_id` | VARCHAR(64) | Yes | - | Subject account |
| `customer_id` | VARCHAR(32) | Yes | - | Subject customer |
| `created_ts` | TIMESTAMP | Yes | - | UTC alert timestamp (trigger txn + 5 minutes) |
| `risk_score` | INTEGER | Yes | - | Calculated risk score clamped to [0, 100] |
| `severity` | VARCHAR(32) | Yes | CRITICAL, HIGH, MEDIUM, LOW | Severity derived from risk_score |
| `priority_rank` | INTEGER | Yes | - | Contiguous 1..N global priority ranking |
| `status` | VARCHAR(32) | Yes | OPEN, CLOSED_TRUE_POSITIVE, CLOSED_FALSE_POSITIVE | Derived alert lifecycle status |
| `case_id` | VARCHAR(32) | Yes | - | Associated investigation case identifier |
| `explanation` | TEXT | Yes | - | Human-readable explainability narrative with parameter values |

## Table: `analyst_actions`
**Description:** Append-only audit trail of analyst workflow operations and findings
**Primary Key:** `action_id`
**Foreign Keys:** `case_id` → `cases.case_id`; `alert_id` → `alerts.alert_id`; `analyst_id` → `analysts.analyst_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `action_id` | VARCHAR(32) | Yes | `^ACT-2026-\d{6}$` | Workflow action event identifier |
| `case_id` | VARCHAR(32) | Yes | - | Subject case identifier |
| `alert_id` | VARCHAR(32) | No | - | Referenced alert identifier (null for case-level actions) |
| `analyst_id` | VARCHAR(16) | Yes | - | Actor analyst identifier |
| `action_type` | VARCHAR(32) | Yes | ASSIGN, REVIEW_START, ESCALATE, DISPOSITION, CLOSE | Action category |
| `disposition` | VARCHAR(32) | No | TRUE_POSITIVE, FALSE_POSITIVE, NEEDS_MORE_INFO | Disposition finding (for DISPOSITION actions) |
| `action_ts` | TIMESTAMP | Yes | - | Timestamp action was executed |
| `note` | TEXT | Yes | - | Structured audit log rationale |

## Table: `analysts`
**Description:** Operational and compliance personnel responsible for triage and disposition
**Primary Key:** `analyst_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `analyst_id` | VARCHAR(16) | Yes | `^ANL-\d{3}$` | Unique analyst personnel identifier |
| `name` | VARCHAR(128) | Yes | - | Analyst full name |
| `role` | VARCHAR(32) | Yes | OPS_ANALYST, RISK_REVIEWER, SYSTEM_ADMIN | Analyst operational role |
| `status` | VARCHAR(32) | Yes | ACTIVE, INACTIVE | Analyst access status |

## Table: `cases`
**Description:** Investigation cases aggregating correlated alerts across time and accounts
**Primary Key:** `case_id`
**Foreign Keys:** `primary_account_id` → `accounts.account_id`; `assigned_analyst_id` → `analysts.analyst_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `case_id` | VARCHAR(32) | Yes | `^CASE-2026-\d{6}$` | Investigation case identifier |
| `primary_account_id` | VARCHAR(64) | Yes | - | Account associated with highest scoring constituent alert |
| `opened_ts` | TIMESTAMP | Yes | - | Case creation timestamp (earliest alert created_ts) |
| `closed_ts` | TIMESTAMP | No | - | Case closure timestamp (null if active) |
| `alert_count` | INTEGER | Yes | - | Number of alerts grouped into this case |
| `case_score` | INTEGER | Yes | - | Composite case risk score clamped to [0, 100] |
| `priority` | VARCHAR(8) | Yes | P1, P2, P3, P4 | Operational priority band |
| `status` | VARCHAR(32) | Yes | OPEN, ASSIGNED, UNDER_REVIEW, ESCALATED, CLOSED | Current case investigation status |
| `assigned_analyst_id` | VARCHAR(16) | No | - | Currently assigned analyst identifier |
| `final_disposition` | VARCHAR(32) | No | TRUE_POSITIVE, FALSE_POSITIVE | Final case outcome (null if unclosed) |

## Table: `customers`
**Description:** Master customer demographic and KYC records
**Primary Key:** `customer_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `customer_id` | VARCHAR(32) | Yes | `^CUS-\d{6}$` | Unique customer identifier |
| `full_name` | VARCHAR(128) | Yes | - | Customer full name (synthetic) |
| `date_of_birth` | DATE | Yes | - | Date of birth (1950-01-01 to 2005-12-31) |
| `email` | VARCHAR(128) | Yes | `^cus-\d{6}@example\.test$` | Unique synthetic email |
| `city` | VARCHAR(64) | Yes | - | Customer city |
| `segment` | VARCHAR(32) | Yes | RETAIL, SALARIED, BUSINESS | Customer segment |
| `kyc_status` | VARCHAR(32) | Yes | VERIFIED, EXPIRED, PENDING | KYC verification status |
| `kyc_risk_tier` | VARCHAR(32) | Yes | LOW, MEDIUM, HIGH | Assigned KYC risk tier |
| `kyc_verified_date` | DATE | No | - | Date KYC was verified; null iff PENDING |
| `kyc_expiry_date` | DATE | No | - | KYC expiration date; null iff PENDING |
| `onboarding_date` | DATE | Yes | - | Customer account relationship start date |

## Table: `devices`
**Description:** Hardware devices and browser instances
**Primary Key:** `device_id`
**Foreign Keys:** `owner_customer_id` → `customers.customer_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `device_id` | VARCHAR(32) | Yes | `^DEV-\d{6}$` | Unique hardware device identifier |
| `device_type` | VARCHAR(32) | Yes | ANDROID, IOS, WEB_BROWSER | Device hardware type |
| `os_family` | VARCHAR(32) | Yes | ANDROID, IOS, WINDOWS, MACOS, LINUX | Operating system family |
| `fingerprint_hash` | VARCHAR(64) | Yes | - | Deterministic 16-hex fingerprint hash |
| `is_emulator` | BOOLEAN | Yes | - | Flag indicating emulated/virtualized environment |
| `status` | VARCHAR(32) | Yes | ACTIVE | Device lifecycle state |
| `first_registered_date` | DATE | Yes | - | Date first registered in the banking channel |
| `owner_customer_id` | VARCHAR(32) | No | - | Owning customer (null for shared/fraud-pool devices) |

## Table: `merchants`
**Description:** Registered merchants and payees
**Primary Key:** `merchant_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `merchant_id` | VARCHAR(32) | Yes | `^MER-\d{6}$` | Unique merchant identifier |
| `merchant_name` | VARCHAR(128) | Yes | - | Trading name of merchant |
| `category` | VARCHAR(32) | Yes | GROCERY, FUEL, ELECTRONICS, TRAVEL, DINING, UTILITIES, ENTERTAINMENT, HEALTHCARE, ECOMMERCE, GAMBLING, CRYPTO_EXCHANGE, JEWELRY | Merchant industry code |
| `risk_level` | VARCHAR(32) | Yes | LOW, MEDIUM, HIGH | Derived category risk tier |
| `city` | VARCHAR(64) | Yes | - | Merchant physical or registered city |
| `onboarding_date` | DATE | Yes | - | Merchant onboarding date |
| `status` | VARCHAR(32) | Yes | ACTIVE, INACTIVE | Merchant processing status |

## Table: `risk_rules`
**Description:** Configuration and threshold definitions for detection rules and score adjustments
**Primary Key:** `rule_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `rule_id` | VARCHAR(16) | Yes | `^[RA]\d{2}$` | Rule code (R01..R05 detection, A01..A04 adjustments) |
| `rule_name` | VARCHAR(64) | Yes | - | Canonical rule name |
| `rule_type` | VARCHAR(32) | Yes | DETECTION, ADJUSTMENT | Rule functional category |
| `description` | VARCHAR(256) | Yes | - | Detailed rule description and trigger condition |
| `base_points` | INTEGER | Yes | - | Base score points contributed (negative for adjustments) |
| `parameters_json` | TEXT | Yes | - | JSON configuration defining operational thresholds |
| `effective_from` | DATE | Yes | - | Rule activation date |
| `effective_to` | DATE | No | - | Rule expiration date (null if active) |
| `status` | VARCHAR(32) | Yes | ACTIVE, INACTIVE | Rule operational status |

## Table: `transactions`
**Description:** Immutable financial ledger transactions
**Primary Key:** `txn_id`
**Foreign Keys:** `account_id` → `accounts.account_id`; `merchant_id` → `merchants.merchant_id`; `device_id` → `devices.device_id`; `counterparty_account_id` → `accounts.account_id`; `transfer_id` → `transfer_links.transfer_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `txn_id` | VARCHAR(32) | Yes | `^TXN-2026-\d{8}$` | Unique transaction reference |
| `account_id` | VARCHAR(64) | Yes | - | Posting account identifier |
| `txn_ts` | TIMESTAMP | Yes | - | UTC transaction timestamp |
| `txn_type` | VARCHAR(32) | Yes | POS_PURCHASE, ATM_WITHDRAWAL, UPI_PAYMENT, BILL_PAYMENT, NEFT_TRANSFER_OUT, TRANSFER_IN, SALARY_CREDIT, CASH_DEPOSIT, REFUND, CLOSURE_PAYOUT | Transaction classification |
| `direction` | VARCHAR(8) | Yes | DEBIT, CREDIT | Cashflow direction |
| `amount` | DECIMAL(15,2) | Yes | - | Absolute transaction value (> 0) |
| `balance_before` | DECIMAL(15,2) | Yes | - | Ledger balance immediately prior to posting |
| `balance_after` | DECIMAL(15,2) | Yes | - | Ledger balance immediately after posting |
| `channel` | VARCHAR(32) | Yes | MOBILE_APP, WEB, POS, ATM, BRANCH, UPI | Execution channel |
| `merchant_id` | VARCHAR(32) | No | - | Referenced merchant identifier |
| `device_id` | VARCHAR(32) | No | - | Referenced hardware device identifier |
| `counterparty_account_id` | VARCHAR(64) | No | - | Referenced counterparty account (internal transfers) |
| `transfer_id` | VARCHAR(32) | No | - | Referenced bilateral transfer link |

## Table: `transfer_links`
**Description:** Bilateral linkages connecting internal transfer debit and credit legs
**Primary Key:** `transfer_id`
**Foreign Keys:** `source_account_id` → `accounts.account_id`; `dest_account_id` → `accounts.account_id`; `debit_txn_id` → `transactions.txn_id`; `credit_txn_id` → `transactions.txn_id`

| Field Name | Type | Required | Allowed Values / Format | Description |
|---|---|---|---|---|
| `transfer_id` | VARCHAR(32) | Yes | `^TRF-2026-\d{6}$` | Bilateral transfer link identifier |
| `source_account_id` | VARCHAR(64) | Yes | - | Originating source account |
| `dest_account_id` | VARCHAR(64) | Yes | - | Destination target account |
| `debit_txn_id` | VARCHAR(32) | Yes | - | Debit ledger transaction reference |
| `credit_txn_id` | VARCHAR(32) | Yes | - | Credit ledger transaction reference |
| `amount` | DECIMAL(15,2) | Yes | - | Agreed transfer amount |
| `initiated_ts` | TIMESTAMP | Yes | - | Timestamp debit leg initiated |
| `settled_ts` | TIMESTAMP | Yes | - | Timestamp credit leg settled |
| `status` | VARCHAR(32) | Yes | SETTLED | Settlement status |
