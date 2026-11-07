# Prompt Engineering and Iteration History

## Prompt Iteration Log

### Prompt 1: Initial Master Prompt Specification
- **Objective:** Build an end-to-end, reproducible, CSV-backed synthetic risk-alert prioritization pipeline in Python 3.10+ using only standard library, pandas, and numpy.
- **Key Requirements:**
  - Seeded random generation (`20261022`) with scale presets (`starter`: 5,000 txns, `full`: 100,000 txns).
  - 15 relational tables with explicit PKs, FKs, types, and regex formats.
  - Transparent rules engine (R01..R05, A01..A04) with explainable additive score breakdown.
  - Case management via union-find alert clustering and simulated analyst lifecycle actions.
  - 5 labelled injected data quality anomalies.
  - SQLite DDL and INSERT exporter with in-memory validation.
  - Automated validation checking 5 acceptance gates and bit-for-bit reproducibility.
- **Outcome:** Generated `requirements.txt`, `config.py`, `schema.py`, `io_utils.py`, `generate.py`, `run_rules.py`, `inject_alert_anomalies.py`, `export_sql.py`.

---

### Prompt 2: Bug Fixes & Refinement
- **Issue 1:** `TypeError: can only concatenate str (not "int") to str` in `run_rules.py` when computing score component points from CSV string values.
  - *Resolution:* Added explicit integer casting `int(r["base_points"])` in `RulesEngine.__init__`.
- **Issue 2:** `ValueError: could not convert string to float: 'False'` in `export_sql.py`.
  - *Resolution:* Added boolean column detection mapping boolean strings to `'1'`/`'0'` before numeric parsing.
- **Issue 3:** Regex check failure in `validate.py` on `ASE-2026-000001` violating `^ASE-\d{6}$`.
  - *Resolution:* Aligned regex pattern in `schema.py` to `^ASE-2026-\d{6}$` matching Section 3 conventions.
- **Issue 4:** Unexpected `NEGATIVE_BALANCE_NO_OD` during ordinary transaction generation.
  - *Resolution:* Added check converting ordinary debits that would breach the overdraft floor into `CASH_DEPOSIT` credits.
- **Issue 5:** Unexpected `TXN_ON_CLOSED_ACCOUNT` in bilateral background transfers.
  - *Resolution:* Enforced candidate target accounts in bilateral transfers to be active and not closed at transaction timestamp.
- **Issue 6:** Full-scale Gate 4 failure (FP representation was 18.9% due to premature device reassignment).
  - *Resolution:* Implemented `account_device_upgrades` map so upgraded devices are only used from `upgrade_ts` onwards, allowing `FP_NEW_DEVICE` to trigger properly. False-positive representation rose to 23.5% (PASS).

---

### Prompt 4: Architecture Simplification & Refactoring
- **Objective:** Refactor pipeline into an interview-explainable, modular architecture where every decision is explainable in 1–2 sentences, functions are $\le 50$ lines, and line counts strictly adhere to project limits.
- **Key Enhancements:**
  - Split `generate.py` into: `gen_master.py` (master entities & status events), `gen_scenarios.py` (planted patterns & anomalies), `gen_transactions.py` (budget allocation & balance sweep), and `generate.py` (orchestrator).
  - Replaced iterative calibration loops with exact count by construction ($N_{bg} = N_{target} - N_{scn} - N_{inj}$) using largest remainder allocation.
  - Strict parameter-driven rules engine with 5 primary rules (`VELOCITY_SPIKE`, `NEW_DEVICE_ACTIVITY`, `CIRCULAR_TRANSFER`, `DORMANT_REACTIVATION`, `AMOUNT_OUTLIER`) and 2 mitigating adjustments (`A01` -40, `A02` -15).
  - 1 rule match = 1 alert; 7-day rolling window case clustering via union-find.
  - Preserved fail-loud balance math: unauthorized overdraft breaches immediately raise a `ValueError`.

---

### Prompt 5: Reconciliation, Background Transfers & Final Verification
- **Objective:** Reconcile alert and case counts, restore background transfers, explain cross-fires, align rule definitions with the spec, and re-test across all scales using `output/`.
- **Key Enhancements & Audits:**
  - Reconciled alert counts: 1,008 baseline alerts + 10 injected anomalies = 1,018 total alerts. Reconciled case counts: 708 baseline cases + 10 injected cases = 718 total cases. Verified zero baseline rows modified.
  - Cross-fire analysis: Proved that all 310 extra alerts are deterministic multi-rule firings on planted high-risk events (e.g. large new-device debit triggering both R02 and R05; dormant reactivation triggering R04, R02, and R05) with 0 unmapped alerts and 0 accidental background noise.
  - Restored background domestic transfers: ~3% of background budget generated as paired domestic transfers (`NEFT_TRANSFER_OUT` + `TRANSFER_IN` with strict $A_{src} < A_{dst}$ DAG ordering). Confirmed acyclic topology where R03 triggers only on planted rings.
  - Fixed `validate.py` sorting: Numerical sorting by `priority_rank.astype(int)` confirmed 100.0% Precision@50, 100.0% Precision@100, and 100.0% Precision@250.
  - Aligned all documentation with INR (₹) currency and canonical rule names.
  - Verified bit-for-bit reproducibility (100% SHA-256 match on all 22 files) on both scales.
