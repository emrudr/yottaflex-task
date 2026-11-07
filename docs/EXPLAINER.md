# Pipeline Architecture & Explainer

This document provides a concise, interview-ready summary of the synthetic risk-alert prioritization pipeline. Every piece of logic is intentionally structured to be explainable in 1–2 sentences.

---

## 1. End-to-End Execution Flow

```
[generate.py]
  ├─ gen_master.py        -> Builds customers, accounts, devices, merchants, analysts
  ├─ gen_scenarios.py     -> Plants true suspicious patterns and benign look-alikes
  └─ gen_transactions.py  -> Allocates exact background event budget & executes balance sweep
        │
        ▼
[run_rules.py]            -> Evaluates detection rules (R01..R05), applies score adjustments
                             (A01, A02), groups alerts into cases via union-find, and simulates
                             analyst review, escalation, and final dispositions
        │
        ▼
[inject_alert_anomalies.py] -> Injects labelled alert-level data quality edge cases (headless
                               alerts, inverted disposition timestamps)
        │
        ▼
[export_sql.py]           -> Exports complete DDL and INSERT statements to seed.sql and verifies
                             relational integrity against an in-memory SQLite database
        │
        ▼
[validate.py]             -> Validates PK, FK, enums, ledger arithmetic, lifecycle state machine,
                             isolated ground-truth recall, and evaluates 5 acceptance gates
```

---

## 2. File-by-File Summary

- **`config.py`**: Central repository for seeds, scale presets (`starter` vs `full`), enum lists, ID formatters, and scenario volume targets. Ensures consistent parameters across all pipeline stages.
- **`schema.py`**: Single source of truth defining table schemas, primary keys, foreign keys, regex patterns, allowed enum values, and the `risk_rules` configuration.
- **`io_utils.py`**: Deterministic CSV and JSON I/O helpers with schema-ordered columns, Unix line endings, SHA-256 calculation, and an environment-guarded ground truth access barrier.
- **`gen_master.py`**: Generates parent entities (`customers`, `merchants`, `analysts`, `devices`) and customer accounts with initial `OPENED` lifecycle status events.
- **`gen_scenarios.py`**: Generates pre-funded suspicious patterns (`TRUE_*`) using non-trusted accounts and benign look-alikes (`FP_*`) using trusted accounts, plus transaction-level anomalies.
- **`gen_transactions.py`**: Distributes exact background transaction budgets across accounts using the largest remainder method, restores ~3% routine domestic transfer pairs (`NEFT_TRANSFER_OUT` + `TRANSFER_IN` with strict acyclic $A_{src} < A_{dst}$ ordering), places events in equal time slices, and executes a chronological balance sweep.
- **`generate.py`**: Top-level orchestrator for Stage 1 that calls `gen_master`, `gen_scenarios`, and `gen_transactions`, syncs account lifecycle states, and saves tables and metadata manifests.
- **`run_rules.py`**: Stateless rules engine that reads strictly observable data, computes explainable risk scores with mitigating adjustments, clusters alerts into cases via union-find, and simulates analyst triage.
- **`inject_alert_anomalies.py`**: Injects labelled alert-level edge cases (`ALERT_NO_TRIGGER`, `DISPOSITION_BEFORE_ALERT`) with separate ground truth labels to test validation audit logic.
- **`export_sql.py`**: Translates CSV tables into SQLite-compliant DDL with CHECK constraints and INSERT statements, verifying zero foreign key violations in memory.
- **`validate.py`**: Comprehensive auditing harness checking structural integrity, chronological ordering, balance arithmetic, and detection recall against ground truth across 5 acceptance gates.
- **`run_all.py`**: Command-line runner that executes the entire pipeline end-to-end in strict sequence.
- **`check_reproducibility.py`**: Determinism tester that executes two independent pipeline runs from scratch and verifies bit-for-bit identical row counts and SHA-256 checksums across all generated files.

---

## 3. Key Design Decisions

1. **Exact Count by Construction:** Background transaction budget is explicitly computed as $N_{target} - N_{scenarios} - N_{injected}$, eliminating non-deterministic count-calibration loops and top-up events.
2. **Deterministic Time-Slicing:** Account events are placed into $K$ equal time slices across their active window, naturally preventing accidental dormancy gaps without heuristic safety nets.
3. **Fail-Loud Ledger Math:** Scenario accounts are pre-funded with explicit credits; if any non-bypass debit breaches the overdraft floor during the balance sweep, an exception is immediately raised.
4. **1 Rule Firing = 1 Alert:** Primary-rule merging and corroboration logic were removed; multiple rules firing on the same transaction produce distinct, explainable alerts grouped by case.
5. **Two Simple Adjustments:** Replaced complex merchant profiling with two clear score modifiers: `A01` ($-40$ for same-owner circular transfers) and `A02` ($-15$ for established, low-risk, verified customers).
6. **Strict Ground Truth Isolation:** Ground truth lives only in `output/ground_truth/` and is protected by runtime environment checks (`ALLOW_GT=1`) to prevent data leakage into detection logic.

