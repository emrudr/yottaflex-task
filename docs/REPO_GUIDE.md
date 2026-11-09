# Repository Guide

This guide explains how the pipeline works, how files connect, and how to verify the results.

---

## 1. Flow in Five Lines

1. **generate**: Creates master records, plants known suspicious patterns and look-alikes, allocates background events, and runs a chronological balance sweep.
2. **run rules**: Reads only the data tables, evaluates five detection rules and two score adjustments, ranks alerts, clusters alerts within seven days into cases, and simulates analyst dispositions.
3. **inject anomalies**: Adds labelled alert and case edge cases to test validation checks.
4. **export sql**: Writes SQLite table definitions and insert statements to seed.sql and verifies relational integrity.
5. **validate**: Checks primary keys, foreign keys, enums, dates, ledger math, lifecycle states, ground truth recall, and five acceptance gates.

---

## 2. File Directory

| File | Purpose |
|---|---|
| `config.py` | Holds global constants, fixed seed 20261022, ID formats, date ranges, and volume presets for starter and full scales. |
| `schema.py` | Defines table structures, primary keys, foreign keys, regex patterns, allowed enums, and default rule definitions. Generates data dictionary markdown. |
| `io_utils.py` | Handles reading and writing CSV and JSON files with ordered columns, calculates SHA-256 hashes, and blocks ground truth access unless ALLOW_GT is set. |
| `gen_master.py` | Generates master entities: customers, accounts with initial OPENED status events, merchants, devices, and analysts. |
| `gen_scenarios.py` | Plants five true suspicious patterns, four false-positive look-alikes, and three transaction-level data problems, writing labels to ground truth. |
| `gen_transactions.py` | Allocates the remaining transaction budget across accounts, generates background domestic transfer pairs, and runs the chronological balance sweep. |
| `generate.py` | Orchestrates master, scenario, and transaction generation, updates account status to the latest event, and writes output tables and data dictionary. |
| `run_rules.py` | Evaluates five detection rules and two mitigating adjustments on data tables, clusters alerts into cases using union-find, and records analyst actions. |
| `inject_alert_anomalies.py` | Injects headless alerts and cases with inverted disposition timestamps, writing separate ground truth labels. |
| `export_sql.py` | Exports all tables to output/sql/seed.sql and verifies foreign keys using an in-memory SQLite database. |
| `validate.py` | Audits structural integrity, ledger balances, lifecycle transitions, detection recall against ground truth, and evaluates five acceptance gates. |
| `run_all.py` | CLI orchestrator that executes generate, run_rules, inject_alert_anomalies, export_sql, and validate in sequence. |
| `check_reproducibility.py` | Runs the entire pipeline twice into separate folders and compares row counts and SHA-256 checksums across all 22 output files. |
| `requirements.txt` | Lists Python package dependencies: pandas and numpy. |
| `README.md` | Plain one-page overview of the project, install steps, run commands, and output summary. |
| `docs/REPO_GUIDE.md` | This file: complete explanation of flow, files, rules, relationships, planted patterns, testing steps, and limits. |
| `docs/data_dictionary.md` | Full field-level specification for all 15 tables, auto-generated from schema.py. |
| `docs/AI_USAGE.md` | Disclosure of AI assistance used in drafting schemas, algorithms, and validation checks. |
| `prompts/prompt_history.md` | Log of prompt iterations and problem statement specifications. |

---

## 3. Rules and Adjustments

The five detection rules and two mitigating adjustments read their parameters from `risk_rules.csv`.

| Rule ID | Rule Name | When It Fires | Base Score | Bonuses |
|---|---|---|---|---|
| R01 | VELOCITY_SPIKE | At least 6 debits on the account within a 60-minute rolling window | 60 | +15 if debits >= 10, +15 if total debit amount >= 50000.0 |
| R02 | NEW_DEVICE_ACTIVITY | First debit on a newly observed device for an account, debit >= 15000.0, and account has >= 5 prior transactions | 55 | +15 if debit amount >= 50000.0, +15 if device is an emulator or shared across >= 3 accounts |
| R03 | CIRCULAR_TRANSFER | Circular transfer path of 2 to 5 hops where funds return to origin account within 72 hours with legs >= 5000.0 | 60 | +20 if >= 3 distinct customers participate, +15 if capital retention ratio >= 0.9 |
| R04 | DORMANT_REACTIVATION | Transaction in either direction >= 10000.0 following an account inactivity gap >= 180 days | 55 | +25 if debit drain ratio >= 0.8 of balance before, +15 if a new hardware device was used |
| R05 | AMOUNT_OUTLIER | Debit >= 25000.0 and >= 8 times the median debit of the account over prior 90 days, with >= 5 prior debits | 45 | +15 if outlier multiplier >= 15 times median, +10 if merchant is HIGH risk |
| A01 | SAME_OWNER_TRANSFER | Applied to R03 circular transfers when all accounts in the loop belong to the same customer | -40 | None |
| A02 | TRUSTED_CUSTOMER | Applied to any rule when customer tenure is >= 3 years, KYC status is VERIFIED, and risk tier is LOW | -15 | None |

Final alert score is clamped between 5 and 100. Severity bands:
- CRITICAL: score >= 85
- HIGH: score 70 to 84
- MEDIUM: score 50 to 69
- LOW: score < 50

---

## 4. Tables and Entity Relationships

The data model consists of 15 relational tables:

1. **customers to accounts (one-to-many, mandatory)**: Each customer has at least 1 primary account (opened on onboarding date) and up to 1 optional secondary account. Every account must belong to exactly one customer.
2. **accounts to transactions (one-to-many, mandatory)**: Accounts hold transaction history. Every transaction references an account. Financial history is append-only and immutable.
3. **accounts to account_status_events (one-to-many, mandatory, keeps history)**: Account lifecycle transitions (OPENED to ACTIVE, ACTIVE to DORMANT, DORMANT to ACTIVE, and ACTIVE or DORMANT to CLOSED) are stored as explicit event rows. The status on the accounts table is derived from the latest event.
4. **accounts and devices via account_devices (many-to-many bridge, optional)**: Accounts interact with devices. The bridge table records first seen time, last seen time, total transaction count, and link status.
5. **customers to devices (one-to-many, optional)**: Personal devices have owner_customer_id set. Shared or emulator devices have owner_customer_id as empty/null.
6. **merchants to transactions (one-to-many, optional)**: POS and UPI purchase debits link to a merchant. Transfers and cash deposits leave merchant_id empty.
7. **transfer_links to transactions (one-to-one per leg, mandatory)**: Each transfer link connects exactly one debit leg (source account) and one credit leg (destination account) with matching transfer_id and settled amounts.
8. **risk_rules to alerts (one-to-many, mandatory)**: Every alert points to its primary triggering rule via rule_id.
9. **alerts and transactions via alert_evidence (many-to-many bridge, optional)**: Links alerts to triggering or supporting transactions. Headless anomaly alerts have zero evidence rows.
10. **alerts to alert_score_components (one-to-many, mandatory, keeps history)**: Stores every additive score contribution (base points, bonuses, and mitigating adjustments) for each alert.
11. **cases to alerts (one-to-many, mandatory)**: Alerts on the same account within a 7-day rolling window are clustered into a single case using union-find.
12. **analysts to cases (one-to-many, optional)**: Operations analysts (ANL-001 to ANL-008) are assigned to investigate cases. Borderline cases are escalated to risk reviewers (ANL-009 to ANL-011). System administrator ANL-012 handles system routing.
13. **cases to analyst_actions (one-to-many, mandatory, keeps history)**: Audit log recording actions taken on a case (ASSIGN, REVIEW_START, ESCALATE, DISPOSITION, CLOSE). Case status is derived from the latest action.
14. **alerts to analyst_actions (one-to-many, optional)**: Analyst actions of type DISPOSITION record the alert_id and disposition (TRUE_POSITIVE or FALSE_POSITIVE).

---

## 5. Planted Patterns and Injected Problems

Planted patterns and data problems are tracked in `output/ground_truth/ground_truth.json` and `ground_truth.csv`. The rules engine never reads these files.

### Planted True Suspicious Scenarios (label: SUSPICIOUS, expected_decision: TRUE_POSITIVE)
1. **TRUE_VELOCITY**: Rapid debit burst of at least 6 transactions within 60 minutes totaling >= 50000.0 on unverified or non-trusted accounts. Caught by R01.
2. **TRUE_NEW_DEVICE**: High-value debit (>= 32000.0) from a newly observed device on an established account with >= 5 prior transactions. Caught by R02.
3. **TRUE_CIRCULAR**: 3-hop transfer ring across distinct customers where funds return to origin within 72 hours. Caught by R03.
4. **TRUE_DORMANT**: Large debit draining 90% of account balance (amount > 50000.0) from a new device after >= 180 days of inactivity. Caught by R04.
5. **TRUE_OUTLIER**: Debit of at least 25000.0 that is >= 8 times the median debit of the account over prior 90 days. Caught by R05.

### Planted False-Positive Look-Alikes (label: BENIGN_LOOKALIKE, expected_decision: FALSE_POSITIVE)
1. **FP_VELOCITY**: Rapid small-amount bill splits under 5000.0 during business hours on trusted customer accounts. Adjustments suppress score below 50.
2. **FP_NEW_DEVICE**: Device replacement by a trusted customer with tenure >= 3 years and verified KYC. Mitigating adjustment A02 (-15) lowers score.
3. **FP_CIRCULAR**: Inter-account circular transfer loop between accounts owned by the same customer. Mitigating adjustment A01 (-40) lowers score.
4. **FP_DORMANT**: Benign incoming salary/cash credit of 20000.0 after dormancy. Does not qualify for debit drain bonus; A02 lowers score.

### Injected Data Quality Problems (label: DATA_QUALITY_ISSUE)
1. **TXN_ON_CLOSED_ACCOUNT** (issue_type: TXN_ON_CLOSED_ACCOUNT): Transaction posted on an account after its status event changed to CLOSED.
2. **NEGATIVE_BALANCE_NO_OD** (issue_type: NEGATIVE_BALANCE_NO_OD): Debit posted on a standard account without overdraft, leaving balance below 0.00.
3. **TRANSFER_LEG_MISMATCH** (issue_type: TRANSFER_LEG_MISMATCH): TransferLink where the credit leg amount differs from the debit leg amount.
4. **ALERT_NO_TRIGGER** (issue_type: ALERT_NO_TRIGGER): Alert inserted with empty trigger_txn_id and no supporting evidence rows.
5. **DISPOSITION_BEFORE_ALERT** (issue_type: DISPOSITION_BEFORE_ALERT): Analyst disposition action timestamp recorded 2 days before the alert created_ts.

---

## 6. How to Check That It Works

Follow these exact steps:

### Step 1: Run the starter dataset
```bash
python run_all.py --scale starter --out output
```
Expected output:
- Generator prints: `5000 txns, 350 accounts, 250 customers`.
- Rules engine prints: `54 alerts, 39 cases, and 176 analyst actions`.
- Alert anomalies print: `Appended 2 headless alerts and 2 inverted disposition cases`.
- SQL export prints: `Foreign key integrity check PASSED (0 violations)`.
- Acceptance gates print:
  - `[PASS] Gate 1: Zero Unexpected Structural Failures`
  - `[PASS] Gate 2: Injected Anomalies Found Exactly as Planted`
  - `[PASS] Gate 3: Detection Recall >= 0.95 for All TRUE Types`
  - `[PASS] Gate 4: Alert Target & FP Representation (>=20%)`
  - `[PASS] Gate 5: Zero Ground Truth Leakage`
- Full pipeline prints: `FULL PIPELINE EXECUTION COMPLETED SUCCESSFULLY`.

### Step 2: Run starter reproducibility test
```bash
python check_reproducibility.py --scale starter --out output
```
Expected output:
- Runs Pipeline Execution A into `output/_repro/run_a` and Pipeline Execution B into `output/_repro/run_b`.
- Compares all 22 output files across data, ground_truth, reports, and sql.
- Prints `MATCH` for all 22 files.
- Prints: `Overall Reproducibility Status: PASS`.

### Step 3: Run the full dataset
```bash
python run_all.py --scale full --out output
```
Expected output:
- Generator prints: `100000 txns, 7000 accounts, 5000 customers`.
- Rules engine prints: `1008 alerts, 708 cases, and 3132 analyst actions`.
- Alert anomalies print: `Appended 5 headless alerts and 5 inverted disposition cases`.
- Total alerts in `alerts.csv` is 1,018 (1,008 baseline + 10 injected).
- Injected anomalies found match: 5 ALERT_NO_TRIGGER, 5 DISPOSITION_BEFORE_ALERT, 10 NEGATIVE_BALANCE_NO_OD, 10 TRANSFER_LEG_MISMATCH, 10 TXN_ON_CLOSED_ACCOUNT.
- Transfer links count in SQLite verification: `1642` (1,452 routine domestic pairs + 190 scenario pairs).
- All five acceptance gates show `[PASS]`.

### Step 4: Run full reproducibility test
```bash
python check_reproducibility.py --scale full --out output
```
Expected output:
- Runs two full executions and compares all 22 output files.
- Prints `MATCH` for all 22 files.
- Prints: `Overall Reproducibility Status: PASS`.

---

## 7. Assumptions and Known Limits

1. **One transaction can raise more than one alert**: Rules evaluate independently. If a single high-value transaction satisfies both R02 (new device >= 15000.0) and R05 (outlier >= 25000.0 and >= 8 times median), both rules fire and generate separate alert records. In full scale, 310 extra baseline alerts are explainable cross-fires of this kind.
2. **Injected negative balance debits trip R05**: The 10 injected NEGATIVE_BALANCE_NO_OD debits use an amount of ~35000.0 to breach the zero overdraft limit. Because 35000.0 exceeds 25000.0 and exceeds 8 times the median, R05 also fires on these 10 debits.
3. **Analyst decisions come from fixed rules**: Analyst dispositions are simulated deterministically based on case score: scores >= 70 become TRUE_POSITIVE, scores < 50 become FALSE_POSITIVE, and scores 50 to 69 are escalated.
4. **Ground truth guard is only a safety switch**: The guard in io_utils.py checks the ALLOW_GT environment variable. It prevents accidental file reads in code; it is not an OS-level sandbox.
5. **Synthetic data with simple amounts**: All customer names, account numbers, and transactions are generated using random seeds and simple uniform distributions. Currency is Indian Rupees (INR) with two decimal places. Real banking phenomena such as currency conversion, tax withholding, or payment gateway network timeouts are not modeled.
