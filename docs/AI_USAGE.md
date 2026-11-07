# AI Usage Disclosure

## 1. Executive Summary

This project implements an end-to-end synthetic banking transaction generator, rule-based risk alert detection system, case triage manager, and validation engine. Generative AI (Antigravity with Google DeepMind agentic models) was used as a pair programming assistant to draft schemas, implement deterministic generation algorithms, formulate detection rules, build validation checks, and verify reproducible test harnesses. All code was audited, verified against strict acceptance criteria, and tested across both starter (5,000 txns) and full (100,000 txns) production scales.

---

## 2. Tools and Models Used

- **Primary AI Agent:** Antigravity (Advanced Agentic Coding system by Google DeepMind).
- **Core Reasoning Engines:** High-capability reasoning models used for architecture design, algorithmic planning, and test-driven validation.
- **Development Environment:** Local Python 3.12 environment running on macOS (Darwin arm64) using strictly standard libraries, `pandas`, and `numpy`.
- **Database Engine:** In-memory SQLite 3 via Python's standard `sqlite3` library for DDL schema validation, constraint testing, and foreign-key integrity auditing.

---

## 3. Scope of Automation and Assisted Tasks

AI assistance was applied across the following stages of the project lifecycle:

1. **Schema Design & Specification Drafting:**
   - Formalized 15 relational tables in `schema.py` as dataclasses with primary keys, foreign keys, regex patterns, enum lists, and nullability constraints.
   - Generated the Markdown data dictionary (`docs/data_dictionary.md`) and rules catalog (`docs/rules.md`).
2. **Deterministic Data Generation (`generate.py`):**
   - Constructed the multi-entity generation graph starting with parent entities (`customers`, `merchants`, `analysts`, `risk_rules`), moving to secondary entities (`accounts`, `devices`), and terminating with event tables (`transactions`, `transfer_links`, `account_status_events`).
   - Implemented named pseudo-random number streams (`random.Random(f"{SEED}:{purpose}")`) to prevent stream pollution and guarantee bit-for-bit reproducibility.
   - Built a sequential chronological balance sweep ensuring strict mathematical invariance ($balance_{after} = balance_{before} \pm amount$) with overdraft floor adherence.
3. **Risk Detection & Case Management (`run_rules.py`):**
   - Implemented 5 primary detection rules (`VELOCITY_SPIKE`, `NEW_DEVICE_ACTIVITY`, `CIRCULAR_TRANSFER`, `DORMANT_REACTIVATION`, `AMOUNT_OUTLIER`) and 2 mitigating adjustments (`A01` same-owner transfer -40, `A02` trusted customer -15).
   - Formulated an explainability breakdown storing every point contribution in `alert_score_components.csv`.
   - Developed disjoint-set (union-find) clustering to group correlated alerts into unified investigation cases.
   - Simulated realistic human operations analyst review flows, SLA-based tier escalations, reviewer reassignments, and final disposition actions.
4. **Data Quality Edge Case Injection (`inject_alert_anomalies.py`):**
   - Planted 5 distinct labelled anomaly types (`TXN_ON_CLOSED_ACCOUNT`, `NEGATIVE_BALANCE_NO_OD`, `TRANSFER_LEG_MISMATCH`, `ALERT_NO_TRIGGER`, `DISPOSITION_BEFORE_ALERT`) without corrupting unrelated baseline records.
5. **Validation & Quality Gate Verification (`validate.py`):**
   - Built an automated auditing engine checking 8 categories of structural, referential, arithmetic, and lifecycle constraints.
   - Computed detection recall, precision, and disposition agreement against isolated ground-truth datasets.
   - Enforced 5 hard acceptance gates.
6. **Reproducibility Test Harness (`check_reproducibility.py`):**
   - Automated dual-run pipeline execution and per-file cryptographic SHA-256 checksum comparisons.

---

## 4. Prompt Engineering and Iteration Strategy

The iteration workflow followed a structured, test-driven methodology:
1. **Master Prompt Formulation:** Complete architectural specification detailing every table, column name, ID regex, rule threshold, scoring rule, and acceptance gate.
2. **Component Execution & Incremental Verification:** Executing individual stages sequentially (`generate.py` $\to$ `run_rules.py` $\to$ `inject_alert_anomalies.py` $\to$ `export_sql.py` $\to$ `validate.py`), inspecting stdout diagnostics, and verifying data directory outputs.
3. **Automated Error Surfacing & Self-Correction:** When unexpected findings occurred during validation, the exact failure condition was isolated and corrected at the source rather than bypassing the test.

---

## 5. Human Review, Code Auditing, and Verification

Every component generated with AI assistance was subject to programmatic verification and auditing:
- **Ledger Invariance:** Verified across 100,000 transactions that no balance drift occurs.
- **Referential Integrity:** Validated across all tables that foreign keys resolve strictly to valid primary key records.
- **Ground Truth Isolation:** Audited `io_utils.py` and `run_rules.py` to ensure the rules engine never imports, reads, or leaks ground truth information.
- **Reproducibility Verification:** Ran two complete pipeline executions in isolated directories; verified that all CSV, JSON, and SQL files yielded identical SHA-256 hashes.

---

## 6. Risks, Limitations, and Mitigation Strategies

| Identified Risk | Potential Impact | Mitigation Strategy Implemented |
|---|---|---|
| **Ground Truth Data Leakage** | Rules engine memorizing labels or scenarios rather than detecting patterns from observable data. | Guarded file access via an environment variable boundary (`ALLOW_GT=1`) checked in `io_utils.load_ground_truth`. Gate 5 audit checks column names for prohibited terms. |
| **Non-Deterministic Iteration** | Different Python runs producing conflicting rows due to set/dict ordering or system time. | Replaced all `set()` iterations with `sorted()`. Eliminated `datetime.now()` in favor of deterministic simulation clocks. Seeded all `random.Random` instances. |
| **Financial Ledger Drift** | Debit/credit transactions leaving accounts in unverified or invalid balance states. | Chronological balance sweep computes `balance_after` from `balance_before` and auto-corrects debits that would violate overdraft limits into cash deposits prior to posting. |
| **Circular Foreign Key Deadlocks** | Relational databases rejecting circular linkages between `transactions` and `transfer_links`. | Applied `DEFERRABLE INITIALLY DEFERRED` to circular foreign keys within transaction blocks in `seed.sql`. |
